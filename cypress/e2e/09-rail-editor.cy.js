/**
 * 3D Rail Editor test - Verify rail editing functionality in 3D mode
 */
describe('Pinball Wizard - 3D Rail Editor', () => {
    beforeEach(() => {
        cy.visit('/')
        cy.waitForConnection()

        // Switch to 3D mode
        cy.get('.switch-view-btn').then($btn => {
            if ($btn.text().includes('Simulator')) {
                cy.wrap($btn).click()
            }
        })

        // Wait for canvas to render
        cy.get('canvas').should('exist')
    })

    it('should display Edit Rails button in 3D mode', () => {
        cy.contains('button', 'Edit Rails').should('be.visible')
    })

    it('should display Switch to 2D button in 3D mode', () => {
        cy.contains('button', 'Switch to 2D').should('be.visible')
    })

    it('should show editor controls when Edit Rails is clicked', () => {
        cy.contains('button', 'Edit Rails').click()

        // Should show Done Editing button
        cy.contains('button', 'Done Editing').should('be.visible')

        // Should show Add Rail button
        cy.contains('button', 'Add Rail').should('be.visible')

        // Should show Delete Selected button (disabled initially)
        cy.contains('button', 'Delete Selected').should('be.visible').and('be.disabled')

        // Should show Object Drawer
        cy.contains('.drawer-title', 'Drag to Add:').should('be.visible')
        cy.contains('.drawer-item', 'Rail').should('be.visible')
        cy.contains('.drawer-item', 'Bumper').should('be.visible')
    })

    it('should hide editor controls when Done Editing is clicked', () => {
        cy.contains('button', 'Edit Rails').click()
        cy.contains('button', 'Done Editing').should('be.visible')

        cy.contains('button', 'Done Editing').click()

        // Should show Edit Rails again
        cy.contains('button', 'Edit Rails').should('be.visible')

        // Should hide editor controls
        cy.contains('button', 'Add Rail').should('not.exist')
        cy.contains('button', 'Delete Selected').should('not.exist')
    })

    it('should toggle between 2D and 3D views', () => {
        // Currently in 3D mode
        cy.contains('button', 'Switch to 2D').should('be.visible')

        // Switch to 2D
        cy.contains('button', 'Switch to 2D').click()

        // Should now show Simulator button
        cy.contains('button', 'Simulator').should('be.visible')

        // Canvas should not exist in 2D mode
        cy.get('canvas').should('not.exist')

        // Switch back to 3D
        cy.contains('button', 'Simulator').click()

        // Should show Switch to 2D again
        cy.contains('button', 'Switch to 2D').should('be.visible')
        cy.get('canvas').should('exist')
    })

    it('should have both buttons grouped together at bottom right', () => {
        // Both buttons should be in the editor-controls container
        cy.get('.editor-controls').within(() => {
            cy.contains('button', 'Edit Rails').should('be.visible')
            cy.contains('button', 'Switch to 2D').should('be.visible')
        })
    })
})
