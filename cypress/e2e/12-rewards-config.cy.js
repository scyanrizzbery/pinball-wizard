describe('Rewards Configuration', () => {
    beforeEach(() => {
        cy.visit('/')
    })

    it('can configure reward values', () => {
        // Ensure settings panel is visible (it's always visible in desktop view)
        cy.get('.settings-panel').should('be.visible')

        // Switch to Training tab
        cy.contains('.tab', 'Training').click()

        // Find Rewards group header and click to expand
        cy.contains('.group-header', 'Rewards').click()

        // Verify Rewards section is expanded
        cy.contains('.group-content', 'Score Log Scale').should('be.visible')

        // Check for specific reward sliders
        const rewards = [
            'Score Log Scale',
            'Combo Increase Factor',
            'Multiplier Increase Factor',
            'Flipper Penalty',
            'Bumper Hit',
            'Drop Target Hit',
            'Rail Hit'
        ]

        rewards.forEach(reward => {
            cy.contains('.slider-label', reward).should('be.visible')
        })

        // Modify a value (e.g., Bumper Hit)
        cy.contains('.slider-label', 'Bumper Hit')
            .parents('.slider-container')
            .find('input[type="range"]')
            .as('bumperSlider')

        // Get initial value
        cy.get('@bumperSlider').invoke('val').then(initialVal => {
            // Ensure we don't exceed max (2.0)
            let newVal = parseFloat(initialVal) + 0.5
            if (newVal > 2.0) newVal = 1.0

            // Trigger change
            cy.get('@bumperSlider')
                .invoke('val', newVal)
                .trigger('input')

            // Verify label updates (assuming label shows value)
            // formatNumber uses 2 decimals for bumper hit
            // We use a regex or partial match because the label contains the text name too
            cy.contains('.slider-label', 'Bumper Hit')
                .should('contain', newVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}))
        })
    })
})

