/**
 * 3D Controls Layout test - Verify 3D mode controls are properly positioned
 */
describe('Pinball Wizard - 3D Controls Layout', () => {
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

    it('should display both control buttons without overlap', () => {
        cy.get('.editor-controls').should('be.visible')

        // Get both buttons
        cy.contains('button', 'Edit Rails').should('be.visible').as('editBtn')
        cy.contains('button', 'Switch to 2D').should('be.visible').as('switchBtn')

        // Check that both buttons are in the controls-row
        cy.get('.controls-row').within(() => {
            cy.contains('button', 'Edit Rails').should('exist')
            cy.contains('button', 'Switch to 2D').should('exist')
        })

        // Verify buttons don't overlap by checking their positions
        cy.get('@editBtn').then($edit => {
            cy.get('@switchBtn').then($switch => {
                const editRect = $edit[0].getBoundingClientRect()
                const switchRect = $switch[0].getBoundingClientRect()

                // Buttons should not overlap horizontally
                // Either editBtn is completely to the left of switchBtn, or vice versa
                const noOverlap = (editRect.right <= switchRect.left) ||
                    (switchRect.right <= editRect.left)

                expect(noOverlap).to.be.true
            })
        })
    })

    it('should not have text wrapping in buttons', () => {
        // Check Edit Rails button
        cy.contains('button', 'Edit Rails').should($btn => {
            const height = $btn.height()
            // Button should be single line (height should be less than 40px for 12px font)
            expect(height).to.be.lessThan(40)
        })

        // Check Switch to 2D button
        cy.contains('button', 'Switch to 2D').should($btn => {
            const height = $btn.height()
            expect(height).to.be.lessThan(40)
        })
    })

    it('should have proper spacing between buttons', () => {
        cy.get('.controls-row').within(() => {
            cy.get('button').should('have.length', 2)
        })

        // Verify gap between buttons
        cy.contains('button', 'Edit Rails').then($edit => {
            cy.contains('button', 'Switch to 2D').then($switch => {
                const editRect = $edit[0].getBoundingClientRect()
                const switchRect = $switch[0].getBoundingClientRect()

                // Calculate gap (assuming Edit Rails is on the left)
                let gap
                if (editRect.right < switchRect.left) {
                    gap = switchRect.left - editRect.right
                } else {
                    gap = editRect.left - switchRect.right
                }

                // Gap should be approximately 10px (allowing some tolerance)
                expect(gap).to.be.within(8, 12)
            })
        })
    })

    it('should position editor-controls at bottom right', () => {
        cy.get('.editor-controls').should($controls => {
            const rect = $controls[0].getBoundingClientRect()
            const viewportWidth = Cypress.config('viewportWidth')
            const viewportHeight = Cypress.config('viewportHeight')

            // Should be near bottom right
            expect(rect.bottom).to.be.closeTo(viewportHeight, 50)
            expect(rect.right).to.be.closeTo(viewportWidth, 50)
        })
    })

    it('should display buttons on same horizontal line', () => {
        cy.contains('button', 'Edit Rails').then($edit => {
            cy.contains('button', 'Switch to 2D').then($switch => {
                const editRect = $edit[0].getBoundingClientRect()
                const switchRect = $switch[0].getBoundingClientRect()

                // Buttons should have similar vertical center positions (within 5px)
                const editCenter = editRect.top + editRect.height / 2
                const switchCenter = switchRect.top + switchRect.height / 2

                expect(Math.abs(editCenter - switchCenter)).to.be.lessThan(5)
            })
        })
    })
})
