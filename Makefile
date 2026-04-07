.PHONY: test clean help setup-test

TEST_SETTINGS_FILE := /tmp/test_settings.yaml

help:
	@echo "Available targets:"
	@echo "  make test       Run all tests"
	@echo "  make clean      Remove test artifacts"

setup-test:
	@mkdir -p /tmp/uploads
	@echo "API_SECRET: test-secret" > $(TEST_SETTINGS_FILE)
	@echo "DB_FILE: /tmp/test.db" >> $(TEST_SETTINGS_FILE)
	@echo "UPLOAD_FOLDER: /tmp/uploads" >> $(TEST_SETTINGS_FILE)
	@echo "DEBUG: false" >> $(TEST_SETTINGS_FILE)

test: setup-test
	SETTINGS=$(TEST_SETTINGS_FILE) python -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	rm -rf tests/files 2>/dev/null || true
	rm -f $(TEST_SETTINGS_FILE) 2>/dev/null || true
