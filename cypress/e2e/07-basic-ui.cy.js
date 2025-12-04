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

        // Check for Ball Physics
        cy.contains('.group-header', 'Ball Physics').as('ballHeader')
        cy.get('@ballHeader').should('be.visible').click()

        // Verify expansion
        cy.get('@ballHeader').find('.arrow').should('have.class', 'rotated')

        // Check first item to ensure expansion worked
        cy.contains('Table Tilt').should('be.visible')

        // Check for Launch Angle slider (scroll if needed)
        cy.contains('Launch Angle').scrollIntoView().should('be.visible')

        // Interact with slider (basic check)
        cy.contains('Launch Angle')
            .parents('.slider-container')
            .find('input[type="range"]')
            .should('be.visible')
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
        cy.contains('button', 'Left').should('be.visible')
        cy.contains('button', 'Right').should('be.visible')
        cy.contains('button', 'Launch').should('be.visible')
        cy.contains('button', 'N Left').should('be.visible')
        cy.contains('button', 'N Right').should('be.visible')
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
