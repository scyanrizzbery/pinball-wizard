describe('Pinball Wizard Basic Tests', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('loads the application', () => {
        cy.get('#app').should('exist')
    })

    // Removed standalone canvas test as it depends on view mode

    it('can open settings and see launch angle slider', () => {
        // Open Settings using the gear button
        cy.get('.sound-toggle-btn').should('be.visible').click()

        // Check for Ball Physics header
        cy.contains('.group-header', 'Ball Physics').as('ballHeader')

        // Settings default to expanded, so we don't need to click to expand
        // Just verify it's visible
        cy.get('@ballHeader').should('be.visible')

        // Check for Launch Angle slider (scroll if needed)
        // Ensure we wait for animation
        cy.wait(500)
        cy.contains('Launch Angle').scrollIntoView().should('be.visible')

        // Interact with slider (basic check)
        cy.contains('Launch Angle')
            .parents('.slider-container')
            .find('input[type="range"]')
            .should('be.visible')
    })

    it('can toggle 3D view', () => {
        // Initial state: 3D Mode (Perspective) active
        // Button should say "Switch to 2D"
        cy.get('.switch-view-btn').should('contain', 'Switch to 2D')

        // Canvas should exist
        cy.get('canvas').should('exist')

        // Click to toggle to 2D
        cy.get('.switch-view-btn').click()

        // Now in 2D mode (Simulator/Video)
        // Button should say "Switch to 3D"
        cy.get('.switch-view-btn').should('contain', 'Switch to 3D')

        // Canvas should probably still exist in DOM but maybe hidden? 
        // Or if viewMode='video', Pinball3D is v-else?
        // In App.vue: v-if="viewMode === 'video'" else Pinball3D. 
        // So canvas should NOT exist.
        cy.get('canvas').should('not.exist')

        // Click back
        cy.get('.switch-view-btn').click()

        // Should be back to 3D
        cy.get('.switch-view-btn').should('contain', 'Switch to 2D')
        cy.get('canvas').should('exist')
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
