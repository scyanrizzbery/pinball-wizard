/**
 * Accessibility test - Basic accessibility checks
 */
describe('Pinball Wizard - Accessibility', () => {
    beforeEach(() => {
        cy.visit('/')
        cy.waitForConnection()
    })

    describe('Semantic HTML', () => {
        it('should have proper heading hierarchy', () => {
            cy.get('h1').should('have.length', 1)
            cy.get('h3').should('have.length.greaterThan', 0)
        })

        it('should have alt text for images', () => {
            cy.get('img').each($img => {
                cy.wrap($img).should('have.attr', 'alt')
            })
        })

        it('should have proper button elements', () => {
            cy.get('button').its('length').should('be.greaterThan', 0)
        })
    })

    describe('Contrast and Colors', () => {
        it('should have readable text on dark background', () => {
            cy.get('body').should('have.css', 'background-color', 'rgb(18, 18, 18)')
            cy.get('body').should('have.css', 'color', 'rgb(224, 224, 224)')
        })

        it('should have visible button states', () => {
            cy.get('.control-btn').first()
                .should('have.css', 'background-color')
                .and('not.equal', 'transparent')
        })
    })

    describe('Touch Targets', () => {
        it('should have adequately sized touch targets on mobile', () => {
            cy.viewport(375, 667)
            cy.reload()
            cy.waitForConnection()
            cy.get('.input-btn').first().then($btn => {
                const height = $btn.height()
                expect(height).to.be.greaterThan(40) // Minimum 40px for touch targets
            })
        })
    })
})
