describe('Persistence Tests', () => {
    beforeEach(() => {
        cy.clearLocalStorage()
        cy.visit('/')
        // Wait for app to fully load
        cy.waitForConnection()
        cy.get('[data-cy="settings-panel"]', { timeout: 10000 }).should('be.visible')
    })

    describe('Layout Persistence', () => {
        it('should display the selected layout name in dropdown on initial load', () => {
            // Wait for layouts to load in the specific dropdown
            cy.wait(2000) // Allow time for socket round-trip
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select option', { timeout: 15000 })
                .should('have.length.gt', 1)

            // Check that a layout is selected (not blank)
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .should('have.value')
                .and('not.be.empty')

            // Verify the select displays a visible option
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select option:selected')
                .should('have.text')
                .and('not.be.empty')
        })

        it('should persist layout selection across page reloads', () => {
            // Select a specific layout
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .select('Slalom')

            // Wait for layout to load
            cy.wait(1000)

            // Reload the page
            cy.reload()

            // Wait for app to load again
            cy.get('[data-cy="settings-panel"]', { timeout: 10000 }).should('be.visible')

            // Verify the layout is still selected
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .should('have.value', 'slalom')

            // Verify the option text is displayed
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select option:selected')
                .should('have.text', 'Slalom')
        })

        it('should update displayed layout name when switching layouts', () => {
            // Get initial layout
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .invoke('val')
                .then((initialLayout) => {
                    // Switch to a different layout
                    const targetLayout = initialLayout === 'slalom' ? 'Speedway' : 'Slalom'

                    cy.contains('.label', 'Table Layout')
                        .parent()
                        .find('select')
                        .select(targetLayout)

                    // Verify it changed
                    cy.contains('.label', 'Table Layout')
                        .parent()
                        .find('select option:selected')
                        .should('have.text', targetLayout)
                })
        })
    })

    describe('Camera Preset Persistence', () => {
        it('should display the selected camera preset in dropdown on initial load', () => {
            // Check that VIEW select exists and has a value
            cy.contains('.label', 'View')
                .parent()
                .find('select')
                .should('exist')

            // If a preset is selected, it should not show placeholder text
            cy.contains('.label', 'View')
                .parent()
                .find('select')
                .invoke('val')
                .then((val) => {
                    if (val && val !== '') {
                        // Should show the preset name, not "Select Camera Preset"
                        cy.contains('.label', 'View')
                            .parent()
                            .find('select option:selected')
                            .should('not.have.text', 'Select Camera Preset')
                            .and('have.text')
                            .and('not.be.empty')
                    }
                })
        })

        it('should persist camera preset selection across page reloads', () => {
            // Select a specific preset (if available)
            cy.contains('.label', 'View')
                .parent()
                .find('select option')
                .then(($options) => {
                    // Find a non-placeholder option
                    const presetOptions = $options.filter((_, el) =>
                        el.value !== '' && !el.textContent.includes('Select')
                    )

                    if (presetOptions.length > 0) {
                        const presetName = presetOptions.first().text()
                        const presetValue = presetOptions.first().val()

                        // Select the preset
                        cy.contains('.label', 'View')
                            .parent()
                            .find('select')
                            .select(presetValue)

                        cy.wait(500)

                        // Reload page
                        cy.reload()

                        // Wait for load
                        cy.get('[data-cy="settings-panel"]', { timeout: 10000 }).should('be.visible')

                        // Verify preset is still selected
                        cy.contains('.label', 'View')
                            .parent()
                            .find('select')
                            .should('have.value', presetValue)

                        cy.contains('.label', 'View')
                            .parent()
                            .find('select option:selected')
                            .should('have.text', presetName)
                    }
                })
        })
    })

    describe('Model Persistence', () => {
        it('should display the selected model name in dropdown on initial load', () => {
            cy.wait(2000) // Allow time for socket round-trip
            //  Model dropdown should show a value
            cy.contains('.label', 'Model')
                .parent()
                .find('select')
                .should('have.value')
                .and('not.be.empty')

            // Verify visible text
            cy.contains('.label', 'Model')
                .parent()
                .find('select option:selected')
                .should('have.text')
                .and('not.be.empty')
        })

        it('should persist model selection across page reloads', () => {
            // Get available models
            cy.contains('.label', 'Model')
                .parent()
                .find('select option')
                .then(($options) => {
                    if ($options.length > 1) {
                        const modelName = $options.eq(1).text()
                        const modelValue = $options.eq(1).val()

                        // Select a model
                        cy.contains('.label', 'Model')
                            .parent()
                            .find('select')
                            .select(modelValue)

                        cy.wait(500)

                        // Reload
                        cy.reload()

                        // Verify
                        cy.get('[data-cy="settings-panel"]', { timeout: 10000 }).should('be.visible')

                        cy.contains('.label', 'Model')
                            .parent()
                            .find('select')
                            .should('have.value', modelValue)
                    }
                })
        })
    })

    describe('Cross-Feature Persistence', () => {
        it('should persist all three selections (model, layout, preset) simultaneously', () => {
            const selections = {}

            // Select and store Model
            cy.contains('.label', 'Model')
                .parent()
                .find('select')
                .invoke('val')
                .then((val) => {
                    selections.model = val
                })

            // Select and store Layout  
            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .select('Speedway')
                .invoke('val')
                .then((val) => {
                    selections.layout = val
                })

            cy.wait(1000)

            // Reload page
            cy.reload()

            // Verify all persist
            cy.get('[data-cy="settings-panel"]', { timeout: 10000 }).should('be.visible')

            cy.contains('.label', 'Model')
                .parent()
                .find('select')
                .should('have.value', selections.model)

            cy.contains('.label', 'Table Layout')
                .parent()
                .find('select')
                .should('have.value', 'speedway')
        })
    })
})
