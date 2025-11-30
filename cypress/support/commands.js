// ***********************************************
// Custom commands for Pinball Wizard E2E tests
// ***********************************************

/**
 * Wait for the app to be connected to the server
 */
Cypress.Commands.add('waitForConnection', () => {
    cy.get('.status-dot', { timeout: 15000 })
        .should('have.class', 'status-connected')
})

/**
 * Wait for video feed to load
 */
Cypress.Commands.add('waitForVideo', () => {
    cy.get('#video-stream', { timeout: 15000 })
        .should('be.visible')
        .and('have.attr', 'src')
        .and('not.be.empty')
})

/**
 * Click a control button (desktop or mobile)
 * @param {string} buttonName - 'left', 'right', 'launch', 'nudge-left', 'nudge-right'
 */
Cypress.Commands.add('clickButton', (buttonName) => {
    const buttonMap = {
        'left': () => cy.contains('button', 'Left').first(),
        'right': () => cy.contains('button', 'Right').first(),
        'launch': () => cy.contains('button', 'Launch').first(),
        'nudge-left': () => cy.contains('button', /Nudge.*L/i).first(),
        'nudge-right': () => cy.contains('button', /Nudge.*R/i).first()
    }

    if (buttonMap[buttonName]) {
        buttonMap[buttonName]().click()
    } else {
        throw new Error(`Unknown button: ${buttonName}`)
    }
})

/**
 * Select an option from a dropdown by label
 * @param {string} label - The dropdown label (e.g., 'Model', 'Layout', 'View')
 * @param {string} value - The option value to select
 */
Cypress.Commands.add('selectDropdown', (label, value) => {
    cy.contains('.control-group, .controls-container', label)
        .find('select')
        .select(value)
})

/**
 * Toggle AI or Auto-Start
 * @param {string} toggle - 'AI' or 'Auto-Start'
 */
Cypress.Commands.add('toggleSetting', (toggle) => {
    cy.contains('button', toggle).click()
})

/**
 * Get current score value
 */
Cypress.Commands.add('getScore', () => {
    return cy.contains('.label', /SCORE/i).first()
        .parent()
        .find('.score-board')
})

/**
 * Get current ball count
 */
Cypress.Commands.add('getBallCount', () => {
    return cy.contains('.label', /BALLS/i)
        .parent()
        .find('.score-board')
})
