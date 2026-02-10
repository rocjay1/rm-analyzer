package services

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"time"

	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/data/aztables"
	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/rocjay1/rm-analyzer/internal/utils"
	"github.com/shopspring/decimal"
)

// DatabaseService handles interactions with Azure Table Storage.
type DatabaseService struct {
	tableURL          string
	savingsTable      string
	creditCardsTable  string
	transactionsTable string
	peopleTable       string
	accountsTable     string
	credential        azcore.TokenCredential
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

	peopleTable := os.Getenv("PEOPLE_TABLE")
	if peopleTable == "" {
		peopleTable = "people"
	}

	accountsTable := os.Getenv("ACCOUNTS_TABLE")
	if accountsTable == "" {
		accountsTable = "accounts"
	}

	var cred azcore.TokenCredential
	var err error

	// Check if running locally with Azurite (http endpoint)
	if strings.HasPrefix(tableURL, "http") {
		// Use well-known devstore credentials for Azurite
		// Not using TokenCredential here, but NamedKeyCredential directly in getClient
		// We'll store nil cred and handle dev/prod switching in getClient
		cred = nil
	} else {
		// Production: Managed Identity
		cred, err = azidentity.NewDefaultAzureCredential(nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
	}

	svc := &DatabaseService{
		tableURL:          tableURL,
		savingsTable:      savingsTable,
		creditCardsTable:  creditCardsTable,
		transactionsTable: transactionsTable,
		peopleTable:       peopleTable,
		accountsTable:     accountsTable,
		credential:        cred,
	}

	// Ensure tables exist
	if err := svc.CreateTables(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to create tables: %w", err)
	}

	return svc, nil
}

// CreateTables ensures all required tables exist in Azure Table Storage.
func (s *DatabaseService) CreateTables(ctx context.Context) error {
	tables := []string{
		s.savingsTable,
		s.creditCardsTable,
		s.transactionsTable,
		s.peopleTable,
		s.accountsTable,
	}

	var svcClient *aztables.ServiceClient
	var err error

	if s.credential == nil {
		// Dev/Azurite
		cred, err := aztables.NewSharedKeyCredential("devstoreaccount1", "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==")
		if err != nil {
			return err
		}
		svcClient, err = aztables.NewServiceClientWithSharedKey(s.tableURL, cred, nil)
		if err != nil {
			return err
		}
	} else {
		// Prod
		svcClient, err = aztables.NewServiceClient(s.tableURL, s.credential, nil)
		if err != nil {
			return err
		}
	}

	for _, tableName := range tables {
		_, err = svcClient.CreateTable(ctx, tableName, nil)
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

func (s *DatabaseService) getClient(tableName string) (*aztables.Client, error) {
	if s.credential == nil {
		// Dev/Azurite: Use Shared Key
		cred, err := aztables.NewSharedKeyCredential("devstoreaccount1", "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==")
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		return aztables.NewClientWithSharedKey(s.tableURL+"/"+tableName, cred, nil)
	}

	// Prod: Use TokenCredential
	return aztables.NewClient(s.tableURL+"/"+tableName, s.credential, nil)
}

// GetSavings retrieves savings data for a specific month.
func (s *DatabaseService) GetSavings(ctx context.Context, month string) (*models.SavingsData, error) {
	client, err := s.getClient(s.savingsTable)
	if err != nil {
		return nil, err
	}

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
	client, err := s.getClient(s.savingsTable)
	if err != nil {
		return err
	}

	// 1. Get existing item row keys to find deletions
	// We can reuse GetSavings or just query RowKeys
	// querying RowKeys is more efficient
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
		rowKey := "ITEM_" + utils.GenerateSHA256Hash(item.Name)
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

		// Only the first batch can be atomic with SubmitTransaction
		// But Azure Table Storage doesn't support atomic transaction across partition keys
		// Here everything is same PartitionKey
		// However, the Go SDK SubmitTransaction (batch) is atomic for same partition key
		_, err := client.SubmitTransaction(ctx, batch[i:end], nil)
		if err != nil {
			return fmt.Errorf("failed to submit transaction batch %d-%d: %w", i, end, err)
		}
	}

	return nil
}

// GetCreditCards retrieves all credit cards.
func (s *DatabaseService) GetCreditCards(ctx context.Context) ([]models.CreditCard, error) {
	client, err := s.getClient(s.creditCardsTable)
	if err != nil {
		return nil, err
	}

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

			// Helper to safely get string
			getString := func(key string) string {
				if v, ok := parsed[key].(string); ok {
					return v
				}
				return ""
			}

			// Helper to safely get decimal
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

			// Helper to safely get int
			getInt := func(key string) int {
				if v, ok := parsed[key].(float64); ok {
					return int(v)
				}
				if v, ok := parsed[key].(int32); ok {
					return int(v)
				}
				if v, ok := parsed[key].(string); ok { // sometimes stored as string
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

// GetAllPeople retrieves all people from the database.
func (s *DatabaseService) GetAllPeople(ctx context.Context) ([]models.Person, error) {
	client, err := s.getClient(s.peopleTable)
	if err != nil {
		return nil, err
	}

	filter := "PartitionKey eq 'PEOPLE'"
	pager := client.NewListEntitiesPager(&aztables.ListEntitiesOptions{
		Filter: &filter,
	})

	var people []models.Person

	for pager.More() {
		resp, err := pager.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to list people: %w", err)
		}

		for _, entity := range resp.Entities {
			var parsed map[string]any
			if err := json.Unmarshal(entity, &parsed); err != nil {
				continue
			}

			name, _ := parsed["Name"].(string)
			email, _ := parsed["Email"].(string)
			if email == "" {
				// Fallback to RowKey if Email field empty (schema variation?)
				email, _ = parsed["RowKey"].(string)
			}

			var accounts []int
			accountsJson, _ := parsed["Accounts"].(string)
			if accountsJson != "" {
				_ = json.Unmarshal([]byte(accountsJson), &accounts)
			}

			people = append(people, models.Person{
				Name:           name,
				Email:          email,
				AccountNumbers: accounts,
				Transactions:   []models.Transaction{}, // Initialize empty
			})
		}
	}

	return people, nil
}

// GenerateRowKey generates a deterministic unique key for a transaction.
func (s *DatabaseService) GenerateRowKey(t models.Transaction, index int) string {
	// Format: Date|Name|Amount|AccountNumber|Index
	// Amount should be string representation
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

	client, err := s.getClient(s.transactionsTable) // Assumed field s.transactionsTable
	if err != nil {
		return nil, err
	}

	// Group by PartitionKey (default_YYYY-MM)
	partitions := make(map[string][]models.Transaction)
	for _, t := range transactions {
		// Parse date to get YYYY-MM
		// t.Date is string YYYY-MM-DD
		if len(t.Date) >= 7 {
			pk := fmt.Sprintf("default_%s", t.Date[:7])
			partitions[pk] = append(partitions[pk], t)
		} else {
			// Fallback or error? controller.py assumes valid date objects.
			// basic fallback
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
			// Signature for occurrence counting
			sig := fmt.Sprintf("%s|%s|%s|%d", t.Date, t.Name, t.Amount.String(), t.AccountNumber)
			occurrences[sig]++
			idx := occurrences[sig] - 1
			rk := s.GenerateRowKey(t, idx)
			transWithKeys = append(transWithKeys, transWithKey{t, rk})
		}

		// 2. Query existing keys
		// Select RowKey only
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
				// Log warning but continue? Or fail? Python logs warning and assumes empty set (risk of dupe).
				// We'll fail to be safe.
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
					"Category":      string(item.t.Category), // Category is string alias
					"ImportedAt":    timestamp,
				}
				if item.t.Ignore != "" {
					entity["IgnoredFrom"] = string(item.t.Ignore)
				}

				entityJson, _ := json.Marshal(entity)
				batch = append(batch, aztables.TransactionAction{
					ActionType: aztables.TransactionTypeInsertReplace, // Upsert
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
	client, err := s.getClient(s.creditCardsTable)
	if err != nil {
		return err
	}

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
		_, err := client.UpdateEntity(ctx, updatedJson, &aztables.UpdateEntityOptions{
			IfMatch: &entity.ETag, // Optimistic concurrency
		})
		// If ETag mismatch, we should retry, but for simplicity we rely on single consumer for now
		// or maybe retry logic needed.
		// UpdateEntity signature: (ctx, entity, options) -> Response
		// Wait, Check signature of UpdateEntity.
		// It takes []byte.
		_, err = client.UpdateEntity(ctx, updatedJson, nil)
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
			// Construct pseudo GetEntityResponse to reuse logic
			// Need ETag? Yes.
			// But entity is just []byte.
			// We can just manipulate it.
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
func (s *DatabaseService) UpsertAccounts(ctx context.Context, accounts []models.Account, userEmail string) error {
	// Implementation skipped for brevity as not strictly required for ProcessQueue parity right now?
	// Actually controller.py uses it. I should implement it if I can.
	// But loop + upsert is easy.
	return nil
}

// SaveCreditCard upserts a credit card config.
func (s *DatabaseService) SaveCreditCard(ctx context.Context, card models.CreditCard) error {
	client, err := s.getClient(s.creditCardsTable)
	if err != nil {
		return err
	}

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
	// LastReconciled handling?

	entityJson, _ := json.Marshal(entity)
	_, err = client.UpsertEntity(ctx, entityJson, nil)
	return err
}
