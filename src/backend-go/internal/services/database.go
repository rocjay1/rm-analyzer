package services

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/data/aztables"
	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
)

// DatabaseService handles interactions with Azure Table Storage.
type DatabaseService struct {
	serviceClient     *aztables.ServiceClient
	savingsTable      string
	creditCardsTable  string
	transactionsTable string
	accountsTable     string
}

// NewDatabaseService creates a new DatabaseService instance.
func NewDatabaseService() (*DatabaseService, error) {
	tableURL := os.Getenv("TABLE_SERVICE_URL")
	if tableURL == "" {
		return nil, fmt.Errorf("TABLE_SERVICE_URL environment variable is required")
	}

	savingsTable := os.Getenv("SAVINGS_TABLE")
	if savingsTable == "" {
		savingsTable = "savings"
	}

	creditCardsTable := os.Getenv("CREDIT_CARDS_TABLE")
	if creditCardsTable == "" {
		creditCardsTable = "creditcards"
	}

	transactionsTable := os.Getenv("TRANSACTIONS_TABLE")
	if transactionsTable == "" {
		transactionsTable = "transactions"
	}

	accountsTable := os.Getenv("ACCOUNTS_TABLE")
	if accountsTable == "" {
		accountsTable = "accounts"
	}

	var client *aztables.ServiceClient

	// Check if running locally with Azurite (http endpoint)
	if isLocal(tableURL) {
		slog.Info("using Azurite credentials for database service")
		name, key := getAzuriteCredentials()
		cred, err := aztables.NewSharedKeyCredential(name, key)
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		var err2 error
		client, err2 = aztables.NewServiceClientWithSharedKey(tableURL, cred, nil)
		if err2 != nil {
			return nil, fmt.Errorf("failed to create table service client with shared key: %w", err2)
		}
	} else {
		// Production: Managed Identity
		slog.Info("using default Azure credentials for database service")
		cred, err := newDefaultAzureCredential()
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
		var err2 error
		client, err2 = aztables.NewServiceClient(tableURL, cred, nil)
		if err2 != nil {
			return nil, fmt.Errorf("failed to create table service client: %w", err2)
		}
	}

	svc := &DatabaseService{
		serviceClient:     client,
		savingsTable:      savingsTable,
		creditCardsTable:  creditCardsTable,
		transactionsTable: transactionsTable,
		accountsTable:     accountsTable,
	}

	// Ensure tables exist
	if err := svc.CreateTables(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to create tables: %w", err)
	}

	slog.Info("database service initialized successfully",
		"table_url", tableURL,
		"savings_table", savingsTable,
		"credit_cards_table", creditCardsTable,
		"transactions_table", transactionsTable,
		"accounts_table", accountsTable,
	)
	return svc, nil
}

// CreateTables ensures all required tables exist in Azure Table Storage.
func (s *DatabaseService) CreateTables(ctx context.Context) error {
	tables := []string{
		s.savingsTable,
		s.creditCardsTable,
		s.transactionsTable,
		s.accountsTable,
	}

	for _, tableName := range tables {
		_, err := s.serviceClient.CreateTable(ctx, tableName, nil)
		if err != nil {
			// Ignore error if table already exists
			var azErr *azcore.ResponseError
			if errors.As(err, &azErr) && azErr.ErrorCode == "TableAlreadyExists" {
				continue
			}
			return fmt.Errorf("failed to create table %s: %w", tableName, err)
		}
	}
	return nil
}

// getClient returns a client for the specified table.
func (s *DatabaseService) getClient(tableName string) *aztables.Client {
	return s.serviceClient.NewClient(tableName)
}

// GetSavings retrieves savings data for a specific month.
func (s *DatabaseService) GetSavings(ctx context.Context, month string) (*models.SavingsData, error) {
	client := s.getClient(s.savingsTable)

	// Filter by PartitionKey
	filter := fmt.Sprintf("PartitionKey eq '%s'", month)
	pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
		Filter: &filter,
	})

	data := &models.SavingsData{
		Items:           []models.SavingsItem{},
		StartingBalance: decimal.Zero,
	}

	for pager.More() {
		resp, err := pager.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to list entities: %w", err)
		}

		for _, entity := range resp.Entities {
			var parsed map[string]any
			if err := json.Unmarshal(entity, &parsed); err != nil {
				continue
			}

			rowKey, _ := parsed["RowKey"].(string)

			if rowKey == "SUMMARY" {
				if val, ok := parsed["StartingBalance"].(float64); ok {
					data.StartingBalance = decimal.NewFromFloat(val)
				}
			} else if strings.HasPrefix(rowKey, "ITEM_") {
				name, _ := parsed["Name"].(string)
				cost := decimal.Zero
				if val, ok := parsed["Cost"].(float64); ok {
					cost = decimal.NewFromFloat(val)
				}
				data.Items = append(data.Items, models.SavingsItem{
					Name: name,
					Cost: cost,
				})
			}
		}
	}

	return data, nil
}

// SaveSavings saves savings data for a month, handing deletions and upserts.
func (s *DatabaseService) SaveSavings(ctx context.Context, month string, data *models.SavingsData) error {
	client := s.getClient(s.savingsTable)

	// 1. Get existing item row keys to find deletions
	filter := fmt.Sprintf("PartitionKey eq '%s'", month)
	selectFields := "RowKey"
	pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
		Filter: &filter,
		Select: &selectFields,
	})

	existingRowKeys := make(map[string]bool)
	for pager.More() {
		resp, err := pager.NextPage(ctx)
		if err != nil {
			return fmt.Errorf("failed to list existing entities: %w", err)
		}
		for _, entity := range resp.Entities {
			var parsed map[string]any
			if err := json.Unmarshal(entity, &parsed); err != nil {
				continue
			}
			if rk, ok := parsed["RowKey"].(string); ok && strings.HasPrefix(rk, "ITEM_") {
				existingRowKeys[rk] = true
			}
		}
	}

	// 2. Prepare operations
	var batch []aztables.TransactionAction

	// New items row keys
	newItemRowKeys := make(map[string]bool)

	// Upsert Summary
	summaryEntity := map[string]any{
		"PartitionKey":    month,
		"RowKey":          "SUMMARY",
		"StartingBalance": data.StartingBalance.InexactFloat64(),
	}
	summaryJson, _ := json.Marshal(summaryEntity)
	batch = append(batch, aztables.TransactionAction{
		ActionType: aztables.TransactionTypeInsertReplace,
		Entity:     summaryJson,
	})

	// Upsert Items
	for _, item := range data.Items {
		h := sha256.Sum256([]byte(item.Name))
		rowKey := "ITEM_" + hex.EncodeToString(h[:])
		newItemRowKeys[rowKey] = true

		itemEntity := map[string]any{
			"PartitionKey": month,
			"RowKey":       rowKey,
			"Name":         item.Name,
			"Cost":         item.Cost.InexactFloat64(),
		}
		itemJson, _ := json.Marshal(itemEntity)
		batch = append(batch, aztables.TransactionAction{
			ActionType: aztables.TransactionTypeInsertReplace,
			Entity:     itemJson,
		})
	}

	// 3. Delete removed items
	for rk := range existingRowKeys {
		if !newItemRowKeys[rk] {
			deleteEntity := map[string]any{
				"PartitionKey": month,
				"RowKey":       rk,
			}
			deleteJson, _ := json.Marshal(deleteEntity)
			batch = append(batch, aztables.TransactionAction{
				ActionType: aztables.TransactionTypeDelete,
				Entity:     deleteJson,
			})
		}
	}

	// 4. Submit batch (chunked by 100)
	const batchSize = 100
	for i := 0; i < len(batch); i += batchSize {
		end := i + batchSize
		if end > len(batch) {
			end = len(batch)
		}

		_, err := client.SubmitTransaction(ctx, batch[i:end], nil)
		if err != nil {
			return fmt.Errorf("failed to submit transaction batch %d-%d: %w", i, end, err)
		}
	}

	return nil
}

// GetCreditCards retrieves all credit cards.
func (s *DatabaseService) GetCreditCards(ctx context.Context) ([]models.CreditCard, error) {
	client := s.getClient(s.creditCardsTable)

	filter := "PartitionKey eq 'CREDIT_CARDS'"
	pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
		Filter: &filter,
	})

	var cards []models.CreditCard

	for pager.More() {
		resp, err := pager.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to list credit cards: %w", err)
		}

		for _, entity := range resp.Entities {
			var parsed map[string]any
			if err := json.Unmarshal(entity, &parsed); err != nil {
				continue
			}

			getString := func(key string) string {
				if v, ok := parsed[key].(string); ok {
					return v
				}
				return ""
			}

			getDecimal := func(key string) decimal.Decimal {
				if v, ok := parsed[key].(string); ok {
					d, _ := decimal.NewFromString(v)
					return d
				}
				if v, ok := parsed[key].(float64); ok {
					return decimal.NewFromFloat(v)
				}
				return decimal.Zero
			}

			getInt := func(key string) int {
				if v, ok := parsed[key].(float64); ok {
					return int(v)
				}
				if v, ok := parsed[key].(int32); ok {
					return int(v)
				}
				if v, ok := parsed[key].(string); ok {
					// parse int
					var i int
					fmt.Sscanf(v, "%d", &i)
					return i
				}
				return 0
			}

			card := models.CreditCard{
				ID:               getString("RowKey"),
				Name:             getString("Name"),
				AccountNumber:    getInt("AccountNumber"),
				CreditLimit:      getDecimal("CreditLimit"),
				DueDay:           getInt("DueDay"),
				StatementBalance: getDecimal("StatementBalance"),
				CurrentBalance:   getDecimal("CurrentBalance"),
				LastReconciled:   getString("LastReconciled"),
			}
			cards = append(cards, card)
		}
	}

	return cards, nil
}

// GenerateRowKey generates a deterministic unique key for a transaction.
func (s *DatabaseService) GenerateRowKey(t models.Transaction, index int) string {
	uniqueString := fmt.Sprintf("%s|%s|%s|%d|%d", t.Date, t.Name, t.Amount.String(), t.AccountNumber, index)
	hash := sha256.Sum256([]byte(uniqueString))
	return hex.EncodeToString(hash[:])
}

// SaveTransactions saves a list of transactions to Azure Table Storage using batched upserts.
// It performs deduplication by checking existing RowKeys.
// Returns a list of transactions that were ACTUALLY new.
func (s *DatabaseService) SaveTransactions(ctx context.Context, transactions []models.Transaction) ([]models.Transaction, error) {
	if len(transactions) == 0 {
		return []models.Transaction{}, nil
	}

	client := s.getClient(s.transactionsTable)

	// Group transactions by partition key (default_YYYY-MM).
	partitions := make(map[string][]models.Transaction)
	for _, t := range transactions {
		if len(t.Date) >= 7 {
			pk := fmt.Sprintf("default_%s", t.Date[:7])
			partitions[pk] = append(partitions[pk], t)
		} else {
			partitions["default_unknown"] = append(partitions["default_unknown"], t)
		}
	}

	var newTransactions []models.Transaction

	for pk, transList := range partitions {
		// 1. Calculate RowKeys
		occurrences := make(map[string]int)
		type transWithKey struct {
			t   models.Transaction
			key string
		}
		var transWithKeys []transWithKey

		for _, t := range transList {
			sig := fmt.Sprintf("%s|%s|%s|%d", t.Date, t.Name, t.Amount.String(), t.AccountNumber)
			occurrences[sig]++
			idx := occurrences[sig] - 1
			rk := s.GenerateRowKey(t, idx)
			transWithKeys = append(transWithKeys, transWithKey{t, rk})
		}

		// 2. Query existing row keys for deduplication
		filter := fmt.Sprintf("PartitionKey eq '%s'", pk)
		selectFields := "RowKey"
		pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
			Filter: &filter,
			Select: &selectFields,
		})

		existingKeys := make(map[string]bool)
		for pager.More() {
			resp, err := pager.NextPage(ctx)
			if err != nil {
				return nil, fmt.Errorf("failed to list existing transactions: %w", err)
			}
			for _, entity := range resp.Entities {
				var parsed map[string]any
				if err := json.Unmarshal(entity, &parsed); err == nil {
					if rk, ok := parsed["RowKey"].(string); ok {
						existingKeys[rk] = true
					}
				}
			}
		}

		// 3. Filter and Prepare Batch
		var batch []aztables.TransactionAction
		timestamp := time.Now().Format(time.RFC3339)

		for _, item := range transWithKeys {
			if !existingKeys[item.key] {
				newTransactions = append(newTransactions, item.t)

				entity := map[string]any{
					"PartitionKey":  pk,
					"RowKey":        item.key,
					"Date":          item.t.Date,
					"Description":   item.t.Name,
					"Amount":        item.t.Amount.InexactFloat64(),
					"AccountNumber": item.t.AccountNumber,
					"Category":      string(item.t.Category),
					"ImportedAt":    timestamp,
				}
				if item.t.Ignore != "" {
					entity["IgnoredFrom"] = string(item.t.Ignore)
				}

				entityJson, _ := json.Marshal(entity)
				batch = append(batch, aztables.TransactionAction{
					ActionType: aztables.TransactionTypeInsertReplace,
					Entity:     entityJson,
				})
			}
		}

		// 4. Submit Batch
		const batchSize = 100
		for i := 0; i < len(batch); i += batchSize {
			end := i + batchSize
			if end > len(batch) {
				end = len(batch)
			}
			_, err := client.SubmitTransaction(ctx, batch[i:end], nil)
			if err != nil {
				return nil, fmt.Errorf("failed to submit transaction batch: %w", err)
			}
		}
	}

	return newTransactions, nil
}

// UpdateCardBalance updates the current balance of a credit card.
func (s *DatabaseService) UpdateCardBalance(ctx context.Context, accountNumber int, delta decimal.Decimal) error {
	client := s.getClient(s.creditCardsTable)

	// Try RowKey = AccountNumber first
	rowKey := fmt.Sprintf("%d", accountNumber)

	// Helper to update entity
	updateEntity := func(entity *aztables.GetEntityResponse) error {
		var parsed map[string]any
		if err := json.Unmarshal(entity.Value, &parsed); err != nil {
			return err
		}

		currentBal := decimal.Zero
		if v, ok := parsed["CurrentBalance"].(float64); ok {
			currentBal = decimal.NewFromFloat(v)
		}

		newBal := currentBal.Add(delta)
		parsed["CurrentBalance"] = newBal.InexactFloat64()

		updatedJson, _ := json.Marshal(parsed)
		_, err := client.UpdateEntity(ctx, updatedJson, nil)
		return err
	}

	resp, err := client.GetEntity(ctx, "CREDIT_CARDS", rowKey, nil)
	if err == nil {
		return updateEntity(&resp)
	}

	// Fallback: Query by AccountNumber
	filter := fmt.Sprintf("PartitionKey eq 'CREDIT_CARDS' and AccountNumber eq %d", accountNumber)
	pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
		Filter: &filter,
	})

	if pager.More() {
		pageResp, err := pager.NextPage(ctx)
		if err != nil {
			return err
		}
		if len(pageResp.Entities) > 0 {
			entityBytes := pageResp.Entities[0]
			var parsed map[string]any
			if err := json.Unmarshal(entityBytes, &parsed); err != nil {
				return err
			}

			currentBal := decimal.Zero
			if v, ok := parsed["CurrentBalance"].(float64); ok {
				currentBal = decimal.NewFromFloat(v)
			}
			newBal := currentBal.Add(delta)
			parsed["CurrentBalance"] = newBal.InexactFloat64()

			updatedJson, _ := json.Marshal(parsed)
			_, err := client.UpdateEntity(ctx, updatedJson, nil)
			return err
		}
	}

	return fmt.Errorf("credit card with account number %d not found", accountNumber)
}

// UpsertAccounts updates accounts from sync data.
// TODO: implement account upsert logic.
func (s *DatabaseService) UpsertAccounts(ctx context.Context, accounts []models.Account, userEmail string) error {
	return nil
}

// SaveCreditCard upserts a credit card config.
func (s *DatabaseService) SaveCreditCard(ctx context.Context, card models.CreditCard) error {
	client := s.getClient(s.creditCardsTable)

	entity := map[string]any{
		"PartitionKey":     "CREDIT_CARDS",
		"RowKey":           card.ID,
		"Name":             card.Name,
		"AccountNumber":    card.AccountNumber,
		"CreditLimit":      card.CreditLimit.InexactFloat64(),
		"DueDay":           card.DueDay,
		"StatementBalance": card.StatementBalance.InexactFloat64(),
		"CurrentBalance":   card.CurrentBalance.InexactFloat64(),
	}

	entityJson, _ := json.Marshal(entity)
	_, err := client.UpsertEntity(ctx, entityJson, nil)
	return err
}

// DeleteCreditCard deletes a credit card by its ID (RowKey).
func (s *DatabaseService) DeleteCreditCard(ctx context.Context, id string) error {
	client := s.getClient(s.creditCardsTable)

	_, err := client.DeleteEntity(ctx, "CREDIT_CARDS", id, nil)
	return err
}
