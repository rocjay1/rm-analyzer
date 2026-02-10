.PHONY: build run clean test

build:
	go build -o handler cmd/handler/main.go

run: build
	func start

clean:
	rm -f handler

test:
	go test ./...
