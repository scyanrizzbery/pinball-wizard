describe('Combo Display', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('should display combo toast when combo count > 0', () => {
        // Wait for app to load
        cy.get('#app-container').should('be.visible')

        // Access the exposed stats object and trigger a combo
        cy.window().then((win) => {
            // Verify stats object is exposed
            expect(win.__APP_STATS__).to.exist

            // Simulate a combo
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 2
            win.__APP_STATS__.combo_timer = 3.0
        })

        // Verify the toast appears
        cy.get('.combo-toast').should('be.visible')

        // Verify content
        cy.get('.combo-toast .count').should('contain', '2x')
        cy.get('.combo-toast .label').should('contain', 'COMBO')

        // Verify it works for 1x as well (since we lowered threshold)
        cy.window().then((win) => {
            win.__APP_STATS__.combo_count = 1
        })

        cy.get('.combo-toast .count').should('contain', '1x')
    })

    it('should display correct visual tiers based on combo count', () => {
        // Tier 1: Yellow/Gold (1-4x)
        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 3
            win.__APP_STATS__.combo_timer = 3.0
        })
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'linear-gradient(180deg, rgb(248, 205, 218) 0%, rgb(245, 175, 25) 100%)')

        // Tier 2: Purple (5-9x)
        cy.window().then((win) => {
            win.__APP_STATS__.combo_count = 7
        })
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'scale(1.25)')
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'linear-gradient(180deg, rgb(218, 34, 255) 0%, rgb(151, 51, 238) 100%)')

        // Tier 3: Blue/Cyan (10x+)
        cy.window().then((win) => {
            win.__APP_STATS__.combo_count = 12
        })
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'scale(1.5)')
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'linear-gradient(180deg, rgb(0, 210, 255) 0%, rgb(58, 123, 213) 100%)')
    })

    it('should hide combo toast when combo is inactive', () => {
        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 5
        })

        cy.get('.combo-toast').should('be.visible')

        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = false
        })

        cy.get('.combo-toast').should('not.exist')
    })
})
