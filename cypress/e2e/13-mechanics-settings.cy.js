
describe('Table Mechanics Settings', () => {
    beforeEach(() => {
        // Visit the app root
        cy.visit('/')
        // Wait for initial load
        cy.contains('Model', { timeout: 10000 }).should('be.visible')
    })

    it('should display Table Mechanics settings when enabled', () => {
        // 1. Switch to Settings tab
        cy.get('.tab').contains('Settings').click()
        cy.get('.tab').contains('Settings').should('have.class', 'active')

        // 2. Ensure Flipper Mechanics is collapsed (default state)
        // Note: We check that the content div immediately following the header does NOT exist/is not visible
        cy.get('.group-header').contains('Flipper Mechanics').next('.group-content').should('not.exist')

        // 3. Find Table Mechanics group (should be visible even if Flipper is collapsed)
        cy.get('.group-header').contains('Table Mechanics').should('be.visible')

        // 4. Expand Table Mechanics group
        cy.get('.group-header').contains('Table Mechanics').click()

        // 5. Verify Sliders exist and have correct labels
        cy.get('.slider-label').contains('Bumper Respawn').should('be.visible')
        cy.get('.slider-label').contains('Drop Target Wait').should('be.visible')

        // 5. Verify default values (approximate checks)
        // Bumper Respawn default is 10.0s
        cy.get('.slider-label').contains('Bumper Respawn').parent().find('span').last().should('contain', '10.0s')

        // Drop Target Wait default is 2.0s
        cy.get('.slider-label').contains('Drop Target Wait').parent().find('span').last().should('contain', '2.0s')

        // 6. Test Interaction (Slider Change)
        // We can't easily check backend without full integration, but we can check UI updates
        // if we had a way to read the input value directly.
        cy.get('.slider-container').contains('Bumper Respawn')
            .parent().find('input[type="range"]')
            .should('have.value', '10')
    })
})
