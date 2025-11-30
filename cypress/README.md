# Cypress E2E Tests

End-to-end tests for the Pinball Wizard application using Cypress.

## Prerequisites

### Local Testing
- Node.js (v14 or higher)
- The Pinball Wizard Flask application running on `http://localhost:5000`

### Docker Testing
- Docker and Docker Compose
- X11 server (for interactive mode on Linux/WSL)

## Installation

### Local Installation

Install Cypress and dependencies:

```bash
npm install
```

### Docker Installation

No installation needed - uses official Cypress Docker image.

## Running Tests

### Option 1: Docker Compose (Recommended)

**Run Headless Tests** (CI/CD mode):

```bash
# Start the app and run tests
docker-compose --profile e2e up --abort-on-container-exit

# Or run tests against already running app
docker-compose up -d pbwizard
docker-compose --profile e2e up cypress
```

```bash
# Start the app and run tests
docker-compose --profile e2e up --abort-on-container-exit

# Or run tests against already running app
docker-compose up -d pbwizard
docker-compose --profile e2e up cypress
```

**Run Interactive Mode** (development with X11):

```bash
# Set up X11 forwarding (WSL/Linux)
export DISPLAY=:0

# Start app
docker-compose up -d pbwizard

# Open Cypress Test Runner
docker-compose --profile e2e-dev up cypress-interactive
```

**Clean Up**:

```bash
docker-compose down
```

### Option 2: Local npm Scripts

**Interactive Mode** (Development):

Open Cypress Test Runner for interactive test development and debugging:

```bash
npm run cy:open
```

This will open the Cypress GUI where you can:
- Select individual test files to run
- See test execution in real-time
- Debug failing tests
- Use Time Travel debugging

### Headless Mode (CI/CD)

Run all tests headlessly in the terminal:

```bash
npm run cy:run
```

Run tests in a specific browser:

```bash
npm run cy:run:chrome
```

Run tests with video output (headed mode):

```bash
npm run cy:run:headed
```

## Test Structure

Tests are organized by functionality:

```
cypress/
├── e2e/
│   ├── 01-smoke.cy.js          # Basic app loading and connectivity
│   ├── 02-ui-elements.cy.js    # UI components visibility
│   ├── 03-interactions.cy.js   # User interactions (buttons, dropdowns, toggles)
│   ├── 04-game-state.cy.js     # Game state updates and displays
│   └── 05-accessibility.cy.js  # Accessibility checks
├── support/
│   ├── commands.js             # Custom Cypress commands
│   └── e2e.js                  # Global test configuration
└── fixtures/                   # Test data (if needed)
```

## Custom Commands

The tests use custom commands for common operations:

- `cy.waitForConnection()` - Wait for WebSocket connection
- `cy.waitForVideo()` - Wait for video feed to load
- `cy.clickButton(name)` - Click a control button by name
- `cy.selectDropdown(label, value)` - Select dropdown option
- `cy.toggleSetting(name)` - Toggle AI or Auto-Start
- `cy.getScore()` - Get current score value
- `cy.getBallCount()` - Get current ball count

## Writing New Tests

Example test structure:

```javascript
describe('Feature Name', () => {
  beforeEach(() => {
    cy.visit('/')
    cy.waitForConnection()
  })

  it('should do something specific', () => {
    // Test implementation
    cy.get('selector').should('exist')
  })
})
```

## Configuration

Cypress configuration is in `cypress.config.js`:

- **baseUrl**: `http://localhost:5000` (Flask app)
- **viewportWidth**: 1280
- **viewportHeight**: 720
- **defaultCommandTimeout**: 10000ms
- **retries**: 2 (in run mode)

Modify these values in `cypress.config.js` if needed.

## Troubleshooting

### Server Not Running

Ensure the Flask application is running on port 5000:

```bash
python main.py
```

### Connection Timeout

If tests fail with connection timeout:
1. Check that the Flask app is accessible at `http://localhost:5000`
2. Verify WebSocket connections are working
3. Increase timeout in `cypress.config.js` if needed

### Video Feed Issues

If video feed tests fail:
1. Ensure the camera/simulator is running
2. Check that video frames are being sent via WebSocket
3. Verify the `#video-stream` element receives `src` updates

## CI/CD Integration

For CI/CD pipelines, use:

```bash
npm run cy:run
```

Set environment variables if needed:

```bash
CYPRESS_BASE_URL=http://your-server:5000 npm run cy:run
```

## Best Practices

1. **Use custom commands** for repeated actions
2. **Wait for elements** before interacting with them
3. **Use data attributes** for test selectors when possible
4. **Keep tests independent** - each test should be able to run alone
5. **Clean up state** - reset application state between tests if needed
6. **Use aliases** for commonly accessed elements

## Resources

- [Cypress Documentation](https://docs.cypress.io)
- [Best Practices](https://docs.cypress.io/guides/references/best-practices)
- [API Reference](https://docs.cypress.io/api/table-of-contents)
