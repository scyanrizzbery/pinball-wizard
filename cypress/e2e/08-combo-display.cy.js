describe('Combo Display', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('should display combo toast when combo count > 5', () => {
        // Wait for app to load
        cy.get('#app-container').should('be.visible')

        // Access the exposed stats object and trigger a combo
        cy.window().then((win) => {
            // Verify stats object is exposed
            expect(win.__APP_STATS__).to.exist

            // Simulate a combo (must be > 5 to show toast)
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 6
            win.__APP_STATS__.combo_timer = 3.0
        })

        // Wait for Vue reactivity
        cy.wait(100)

        // Verify the toast appears
        cy.get('.combo-toast').should('be.visible')

        // Verify content
        cy.get('.combo-toast .count').should('contain', '6x')
        cy.get('.combo-toast .label').should('contain', 'COMBO')

        // Test with higher combo
        cy.window().then((win) => {
            win.__APP_STATS__.combo_count = 10
        })

        cy.wait(100)
        cy.get('.combo-toast .count').should('contain', '10x')
    })

    it('should display correct visual tiers based on combo count', () => {
        // Tier 2: Purple (5-9x) - note: toast only shows for > 5
        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 7
            win.__APP_STATS__.combo_timer = 3.0
        })

        cy.wait(100)
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'scale(1.25)')
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'linear-gradient(180deg, rgb(218, 34, 255) 0%, rgb(151, 51, 238) 100%)')

        // Tier 3: Blue/Cyan (10x+)
        cy.window().then((win) => {
            win.__APP_STATS__.combo_count = 12
        })

        cy.wait(100)
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'scale(1.5)')
        cy.get('.combo-toast .count').should('have.attr', 'style').and('contain', 'linear-gradient(180deg, rgb(0, 210, 255) 0%, rgb(58, 123, 213) 100%)')
    })

    it('should hide combo toast when combo is inactive', () => {
        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = true
            win.__APP_STATS__.combo_count = 6
        })

        cy.wait(100)
        cy.get('.combo-toast').should('be.visible')

        cy.window().then((win) => {
            win.__APP_STATS__.combo_active = false
        })

        cy.wait(100)
        cy.get('.combo-toast').should('not.exist')
    })
})
