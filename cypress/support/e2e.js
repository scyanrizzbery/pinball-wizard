// ***********************************************************
// This support file is processed and loaded automatically before test files.
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands'

// Alternatively you can use CommonJS syntax:
// require('./commands')

// Prevent Cypress from failing tests on uncaught exceptions
Cypress.on('uncaught:exception', (err, runnable) => {
    // returning false here prevents Cypress from failing the test
    // useful for handling expected errors from the app
    return false
})
