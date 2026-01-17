.PHONY: run lint format install app build clean zip dmg \
	check-version check-clean check-on-main check-no-existing-tag check-gh-auth \
	release release-draft

MODEL_DIR = ~/.local/share/whisper-dictation

run:
	uv run python main.py

install-model:
	@mkdir -p $(MODEL_DIR)
	@echo "Downloading English whisper model (ggml-small.en.bin ~466MB)..."
	@curl -L -o $(MODEL_DIR)/ggml-small.en.bin \
		https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
	@echo "Done. Model installed to $(MODEL_DIR)"

app:
	uv sync --extra dev
	uv run pyinstaller Dictator.spec --noconfirm

build: app
	@rm -rf /Applications/Dictator.app
	@cp -r dist/Dictator.app /Applications/
	@echo "Installed to /Applications/Dictator.app"

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	rm -rf build dist __pycache__ *.egg-info

# === Release Configuration ===
APP_NAME := Dictator
DIST_DIR := dist
RELEASE_DIR := releases
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d '"' -f 2)
TAG := v$(VERSION)
ZIP_NAME := $(RELEASE_DIR)/$(APP_NAME)-$(VERSION)-macos.zip
DMG_NAME := $(RELEASE_DIR)/$(APP_NAME)-$(VERSION)-macos.dmg

# === Distribution Archives ===
zip: app
	@mkdir -p $(RELEASE_DIR)
	@rm -f $(ZIP_NAME)
	@chmod +x $(DIST_DIR)/$(APP_NAME).app/Contents/MacOS/$(APP_NAME)
	cd $(DIST_DIR) && ditto -c -k --keepParent $(APP_NAME).app ../$(ZIP_NAME)
	@echo "Created $(ZIP_NAME) ($$(du -h $(ZIP_NAME) | cut -f1))"

dmg: app
	@mkdir -p $(RELEASE_DIR)
	@rm -f $(DMG_NAME)
	hdiutil create -volname "$(APP_NAME)" -srcfolder $(DIST_DIR)/$(APP_NAME).app \
		-ov -format UDZO $(DMG_NAME)
	@echo "Created $(DMG_NAME) ($$(du -h $(DMG_NAME) | cut -f1))"

# === Pre-release Checks ===
check-version:
	@if ! echo "$(VERSION)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: Invalid version format '$(VERSION)'. Expected x.y.z"; \
		exit 1; \
	fi

check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory has uncommitted changes:"; \
		git status --short; \
		exit 1; \
	fi

check-on-main:
	@if [ "$$(git branch --show-current)" != "main" ]; then \
		echo "Error: Releases must be made from the main branch."; \
		echo "Current branch: $$(git branch --show-current)"; \
		exit 1; \
	fi

check-no-existing-tag:
	@if git tag | grep -q "^$(TAG)$$"; then \
		echo "Error: Tag $(TAG) already exists."; \
		echo "Update version in pyproject.toml before releasing."; \
		exit 1; \
	fi

check-gh-auth:
	@if ! gh auth status >/dev/null 2>&1; then \
		echo "Error: Not authenticated with GitHub CLI."; \
		echo "Run 'gh auth login' first."; \
		exit 1; \
	fi

# === Release ===
release: check-version check-clean check-on-main check-no-existing-tag check-gh-auth
	@echo "============================================"
	@echo "  Releasing $(APP_NAME) $(TAG)"
	@echo "============================================"
	@echo ""
	@echo "[1/5] Building application..."
	@$(MAKE) app
	@echo ""
	@echo "[2/5] Creating DMG..."
	@$(MAKE) dmg
	@echo ""
	@echo "[3/5] Creating git tag $(TAG)..."
	git tag -a $(TAG) -m "Release $(TAG)"
	@echo ""
	@echo "[4/5] Pushing tag to origin..."
	git push origin $(TAG)
	@echo ""
	@echo "[5/5] Creating GitHub release..."
	gh release create $(TAG) \
		"$(DMG_NAME)#$(APP_NAME) $(VERSION) (DMG)" \
		--title "$(APP_NAME) $(TAG)" \
		--generate-notes
	@echo ""
	@echo "============================================"
	@echo "  Release $(TAG) complete!"
	@echo "============================================"
	@echo ""
	@echo "View release: $$(gh release view $(TAG) --json url -q .url)"

release-draft: check-version check-clean check-on-main check-no-existing-tag check-gh-auth
	@echo "Creating draft release for $(TAG)..."
	@$(MAKE) dmg
	git tag -a $(TAG) -m "Release $(TAG)"
	git push origin $(TAG)
	gh release create $(TAG) \
		"$(DMG_NAME)#$(APP_NAME) $(VERSION) (DMG)" \
		--title "$(APP_NAME) $(TAG)" \
		--generate-notes \
		--draft
	@echo ""
	@echo "Draft release created. Review and publish at:"
	@echo "$$(gh release view $(TAG) --json url -q .url)"
