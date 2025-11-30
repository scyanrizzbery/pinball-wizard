# E2E Testing with Docker Compose - Quick Start

## TL;DR

```bash
# Run all E2E tests in Docker
docker-compose --profile e2e up --abort-on-container-exit
```

## Detailed Commands

### 1. Run Tests (Headless)

**Start app and run tests together:**
```bash
docker-compose --profile e2e up --abort-on-container-exit
```

**Or run against already running app:**
```bash
# Start app in background
docker-compose up -d pbwizard

# Run tests
docker-compose --profile e2e up cypress

# Clean up
docker-compose down
```

### 2. Interactive Development (with X11)

**Linux/WSL:**
```bash
# Enable X11 forwarding
export DISPLAY=:0
xhost +local:docker  # Allow Docker to connect to X server

# Start app
docker-compose up -d pbwizard

# Open Cypress Test Runner
docker-compose --profile e2e-dev up cypress-interactive

# Clean up
docker-compose down
```

**Windows (with VcXsrv or similar):**
```bash
# Start VcXsrv with "Disable access control" option

# Set display
export DISPLAY=host.docker.internal:0

# Start app
docker-compose up -d pbwizard

# Open Cypress Test Runner  
docker-compose --profile e2e-dev up cypress-interactive
```

### 3. View Test Results

**Videos and Screenshots:**
Test artifacts are saved to:
- `cypress/videos/` - Test execution videos
- `cypress/screenshots/` - Failure screenshots

**Console Output:**
Test results appear in the terminal where you ran the docker-compose command.

## Architecture

```
┌─────────────────┐
│   pbwizard      │  Flask app on port 5000
│   (Python)      │
└────────┬────────┘
         │
         │ http://pbwizard:5000
         │
┌────────┴────────┐
│   cypress       │  Cypress tests
│   (Node.js)     │
└─────────────────┘
```

Both services run on the same Docker network (`pbwizard-network`).

## Profiles

- **`e2e`** - Headless test execution (CI/CD)
- **`e2e-dev`** - Interactive Test Runner (requires X11)

## Common Issues

### Issue: Tests fail with connection timeout
**Solution:** Ensure Flask app is fully started before running tests:
```bash
docker-compose up -d pbwizard
sleep 5  # Wait for app to be ready
docker-compose --profile e2e up cypress
```

### Issue: Interactive mode doesn't open
**Solution:** Check X11 forwarding:
```bash
echo $DISPLAY  # Should show :0 or similar
xhost +local:docker  # Allow Docker to connect
```

### Issue: Permission denied on videos/screenshots
**Solution:** Fix permissions:
```bash
sudo chown -R $USER:$USER cypress/videos cypress/screenshots
```

## CI/CD Integration

**GitHub Actions example:**
```yaml
- name: Run E2E Tests
  run: docker-compose --profile e2e up --abort-on-container-exit --exit-code-from cypress
```

**GitLab CI example:**
```yaml
e2e-tests:
  script:
    - docker-compose --profile e2e up --abort-on-container-exit
  artifacts:
    paths:
      - cypress/videos/
      - cypress/screenshots/
    when: on_failure
```

## Customization

Edit `docker-compose.yml` to:
- Change Cypress version: Update `image: cypress/included:X.X.X`
- Add environment variables: Add to `environment:` section
- Mount additional volumes: Add to `volumes:` section

## See Also

- Full docs: `cypress/README.md`
- Cypress config: `cypress.config.js`
- Test files: `cypress/e2e/*.cy.js`
