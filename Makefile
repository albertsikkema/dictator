.PHONY: run lint format install app build clean zip dmg generate-icons install-model install-model-multilingual \
	install-models notarize \
	reset-permissions \
	check-version check-clean check-on-main check-no-existing-tag check-gh-auth \
	release release-draft test
MODEL_DIR = $(HOME)/.local/share/whisper-dictation
MODEL_URL = https://huggingface.co/ggerganov/whisper.cpp/resolve/main
BUNDLE_ID = com.dictator.app

# Code signing identity: a self-signed certificate in the login keychain, or
# a "Developer ID Application: ..." certificate for builds others can open.
# Without one the app is signed ad hoc, and macOS drops its permissions on
# every rebuild. See "Code signing" in README.md.
SIGN_IDENTITY ?= Dictator Local Signing

# notarytool credentials, stored once with `xcrun notarytool store-credentials`
NOTARY_PROFILE ?= dictator-notary

# Releases signed with a Developer ID are notarized; others are not
ifneq (,$(findstring Developer ID Application,$(SIGN_IDENTITY)))
RELEASE_DMG_TARGET := notarize
else
RELEASE_DMG_TARGET := dmg
endif

run:
	uv run python main.py

# Models are file targets, so make skips any that are already downloaded
install-model: $(MODEL_DIR)/ggml-small.en.bin            # English, ~466MB
install-model-multilingual: $(MODEL_DIR)/ggml-medium-q5_0.bin  # Dutch/Auto, ~539MB
install-models: install-model install-model-multilingual

$(MODEL_DIR)/%.bin:
	@mkdir -p $(MODEL_DIR)
	@echo "Downloading whisper model $*.bin..."
	@curl -fL --retry 2 -o $@.part $(MODEL_URL)/$*.bin
	@mv $@.part $@
	@echo "Done. Model installed to $@"

generate-icons:
	uv run python generate_icons.py

app: generate-icons
	@mkdir -p models
	uv sync --extra dev
	@if security find-identity -p codesigning 2>/dev/null | grep -qF '"$(SIGN_IDENTITY)"'; then \
		echo "Signing with \"$(SIGN_IDENTITY)\""; \
		DICTATOR_SIGN_IDENTITY="$(SIGN_IDENTITY)" uv run pyinstaller Dictator.spec --noconfirm; \
	else \
		echo "Warning: signing identity \"$(SIGN_IDENTITY)\" not found, signing ad hoc."; \
		echo "macOS will drop Dictator's permissions after this build (see README.md)."; \
		uv run pyinstaller Dictator.spec --noconfirm; \
	fi

build: app install-models
	@rm -rf /Applications/Dictator.app
	@ditto dist/Dictator.app /Applications/Dictator.app
	@echo "Installed to /Applications/Dictator.app"

# Forget Dictator's privacy permissions, e.g. after an ad-hoc signed rebuild
reset-permissions:
	-tccutil reset Accessibility $(BUNDLE_ID)
	-tccutil reset ListenEvent $(BUNDLE_ID)
	-tccutil reset Microphone $(BUNDLE_ID)

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run --extra test pytest --cov --cov-report=term-missing --cov-report=json
	uv run --extra test python scripts/check_coverage.py
	@rm -f coverage.json

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

# Sign, notarize and staple the DMG (needs a Developer ID SIGN_IDENTITY)
notarize: dmg
	codesign --force --timestamp --sign "$(SIGN_IDENTITY)" $(DMG_NAME)
	xcrun notarytool submit $(DMG_NAME) --keychain-profile "$(NOTARY_PROFILE)" --wait
	xcrun stapler staple $(DMG_NAME)
	spctl --assess --type open --context context:primary-signature --verbose $(DMG_NAME)

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

# === Release Notes Extraction ===
# Extract changelog section for current version
RELEASE_NOTES_FILE := $(RELEASE_DIR)/.release-notes.md
define extract_changelog
	@mkdir -p $(RELEASE_DIR)
	@awk '/^## \[$(VERSION)\]/{found=1; next} /^## \[/{if(found) exit} found{print}' CHANGELOG.md > $(RELEASE_NOTES_FILE)
	@if [ ! -s $(RELEASE_NOTES_FILE) ]; then \
		echo "Warning: No changelog entry found for version $(VERSION)"; \
		echo "Using default release notes."; \
		echo "Release $(TAG)" > $(RELEASE_NOTES_FILE); \
	fi
endef

# === Release ===
release: check-version check-clean check-on-main check-no-existing-tag check-gh-auth
	@echo "============================================"
	@echo "  Releasing $(APP_NAME) $(TAG)"
	@echo "============================================"
	@echo ""
	@echo "[1/6] Building application..."
	@$(MAKE) app
	@echo ""
	@echo "[2/6] Creating DMG..."
	@$(MAKE) $(RELEASE_DMG_TARGET)
	@echo ""
	@echo "[3/6] Extracting release notes from CHANGELOG.md..."
	$(extract_changelog)
	@cat $(RELEASE_NOTES_FILE)
	@echo ""
	@echo "[4/6] Creating git tag $(TAG)..."
	git tag -a $(TAG) -m "Release $(TAG)"
	@echo ""
	@echo "[5/6] Pushing tag to origin..."
	git push origin $(TAG)
	@echo ""
	@echo "[6/6] Creating GitHub release..."
	gh release create $(TAG) \
		"$(DMG_NAME)#$(APP_NAME) $(VERSION) (DMG)" \
		--title "$(APP_NAME) $(TAG)" \
		--notes-file $(RELEASE_NOTES_FILE)
	@rm -f $(RELEASE_NOTES_FILE)
	@echo ""
	@echo "============================================"
	@echo "  Release $(TAG) complete!"
	@echo "============================================"
	@echo ""
	@echo "View release: $$(gh release view $(TAG) --json url -q .url)"

release-draft: check-version check-clean check-on-main check-no-existing-tag check-gh-auth
	@echo "Creating draft release for $(TAG)..."
	@$(MAKE) $(RELEASE_DMG_TARGET)
	$(extract_changelog)
	git tag -a $(TAG) -m "Release $(TAG)"
	git push origin $(TAG)
	gh release create $(TAG) \
		"$(DMG_NAME)#$(APP_NAME) $(VERSION) (DMG)" \
		--title "$(APP_NAME) $(TAG)" \
		--notes-file $(RELEASE_NOTES_FILE) \
		--draft
	@rm -f $(RELEASE_NOTES_FILE)
	@echo ""
	@echo "Draft release created. Review and publish at:"
	@echo "$$(gh release view $(TAG) --json url -q .url)"
