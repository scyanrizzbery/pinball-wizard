describe('Pinball Wizard Basic Tests', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('loads the application', () => {
        cy.get('#app').should('exist')
    })

    // Removed standalone canvas test as it depends on view mode

    it('can open settings and see launch angle slider', () => {
        // Open Settings
        cy.get('.tab').contains('Settings').should('be.visible').click()

        // Check for Physics Settings
        cy.contains('Physics Settings').should('be.visible').click()

        // Check for Launch Angle slider
        cy.contains('Launch Angle').should('be.visible')

        // Interact with slider (basic check)
        cy.contains('Launch Angle')
            .parent()
            .find('input[type="range"]')
            .should('exist')
    })

    it('can toggle 3D view', () => {
        // Initial state: Video Feed active
        // Button should say "Simulator"
        cy.get('.switch-view-btn').should('contain', 'Simulator')

        // Canvas should NOT exist yet (unless in simulation mode)
        cy.get('canvas').should('not.exist')

        // Click to toggle to 3D
        cy.get('.switch-view-btn').click()

        // Now in 3D mode
        // Button should say "Switch to 2D"
        cy.get('.switch-view-btn').should('contain', 'Switch to 2D')

        // Canvas should now exist
        cy.get('canvas').should('exist')

        // Click back
        cy.get('.switch-view-btn').click()

        // Should be back to Video Feed
        cy.get('.switch-view-btn').should('contain', 'Simulator')
    })

    it('displays game controls', () => {
        cy.contains('button', 'Left Flipper').should('be.visible')
        cy.contains('button', 'Right Flipper').should('be.visible')
        cy.contains('button', 'Launch').should('be.visible')
        cy.contains('button', 'Nudge Left').should('be.visible')
        cy.contains('button', 'Nudge Right').should('be.visible')
    })

    it('displays scoreboard', () => {
        cy.get('.scoreboard-container').should('exist')
        cy.contains('SCORE').should('exist')
        cy.contains('HIGH SCORE').should('exist')
    })

    it('displays game history chart', () => {
        cy.get('#history-container').should('exist')
        // Check for Highcharts container
        cy.get('.highcharts-container').should('exist')
    })

    it('displays logs panel', () => {
        cy.get('.game-log-container').should('exist')
    })
})
