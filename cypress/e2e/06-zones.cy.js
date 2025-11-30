describe('Multi-Zone Support', () => {
    beforeEach(() => {
        // Visit the app
        cy.visit('/')
        // Wait for socket connection
        cy.contains('Connected to server', { timeout: 10000 }).should('be.visible')
        // Wait for physics config to load (ensures zones are populated)
        cy.contains('Physics config loaded', { timeout: 10000 }).should('be.visible')
    })

    it('should render default zones', () => {
        // Open Zone Editor
        cy.contains('Edit Zones').click()

        // Check for zone polygons
        cy.get('.zone-poly').should('have.length.at.least', 2)
        cy.get('.zone-poly.left-zone').should('exist')
        cy.get('.zone-poly.right-zone').should('exist')
    })

    it('should allow adding and removing zones', () => {
        cy.contains('Edit Zones').click()

        // Count initial zones
        cy.get('.zone-poly').then($zones => {
            const initialCount = $zones.length

            // Add Left Zone
            cy.contains('+ Left Zone').click()
            cy.get('.zone-poly').should('have.length', initialCount + 1)

            // Add Right Zone
            cy.contains('+ Right Zone').click()
            cy.get('.zone-poly').should('have.length', initialCount + 2)

            // Remove a zone (click the delete button of the last added zone)
            // We need to force click because it might be overlapping or hidden by hover logic
            cy.get('.delete-btn').last().click({ force: true })
            cy.get('.zone-poly').should('have.length', initialCount + 1)
        })
    })

    it('should handle zone dragging', () => {
        cy.contains('Edit Zones').click()

        // Get the first zone polygon
        cy.get('.zone-poly').first().then($poly => {
            const initialPoints = $poly.attr('points')

            // Simulate drag on the body
            cy.wrap($poly)
                .trigger('mousedown', { button: 0, force: true })
                .trigger('mousemove', { clientX: 100, clientY: 100, force: true })
                .trigger('mouseup', { force: true })

            // Verify points changed
            cy.get('.zone-poly').first().should($newPoly => {
                expect($newPoly.attr('points')).not.to.equal(initialPoints)
            })
        })
    })

    it('should reset zones to default', () => {
        cy.contains('Edit Zones').click()

        // Add a zone to modify state
        cy.contains('+ Left Zone').click()
        cy.get('.zone-poly').should('have.length.at.least', 3)

        // Click Reset Zones
        cy.contains('Reset Zones').click()

        // Verify zones revert to default (2 zones)
        cy.get('.zone-poly').should('have.length', 2)
        cy.get('.zone-poly.left-zone').should('exist')
        cy.get('.zone-poly.right-zone').should('exist')
    })
})
