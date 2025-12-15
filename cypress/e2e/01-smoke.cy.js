/**
 * Smoke test - Basic application loading and connectivity
 */
describe('Pinball Wizard - Smoke Test', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('should load the application', () => {
        cy.contains('h1', 'Pinball Wizard').should('be.visible')
    })

    it('should connect to the server', () => {
        cy.waitForConnection()
        cy.get('.connection-status').should('contain', 'Connected')
    })

    it('should load the video feed', () => {
        // Switch to 2D view if not already (robust check)
        cy.get('button').contains(/(2D|3D) View/).then($btn => {
            if ($btn.text().includes('Switch to 2D')) {
                cy.wrap($btn).click()
            }
        })
        cy.waitForVideo()
    })

    it('should display all main UI sections', () => {
        // Game area
        cy.get('#game-area').should('be.visible')

        // Controls
        cy.get('.controls-container, #input-area').should('exist')

        // Settings tab
        cy.get('#physics-controls').should('be.visible')

        // History
        cy.get('#history-container').should('be.visible')
    })
})
