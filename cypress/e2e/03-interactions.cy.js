/**
 * Interactions test - Test user interactions with controls
 */
describe('Pinball Wizard - Interactions', () => {
    beforeEach(() => {
        cy.visit('/')
        cy.waitForConnection()
    })

    describe('Button Interactions', () => {
        it('should highlight left flipper button when pressed', () => {
            cy.contains('button', /Left.*Flip/i).first()
                .as('leftButton')

            cy.get('@leftButton')
                .trigger('mousedown')
                .should('have.class', 'pressed')

            cy.get('@leftButton')
                .trigger('mouseup')
                .should('not.have.class', 'pressed')
        })

        it('should highlight right flipper button when pressed', () => {
            cy.contains('button', /Right.*Flip/i).first()
                .as('rightButton')

            cy.get('@rightButton')
                .trigger('mousedown')
                .should('have.class', 'pressed')

            cy.get('@rightButton')
                .trigger('mouseup')
                .should('not.have.class', 'pressed')
        })

        it('should highlight launch button when pressed', () => {
            cy.contains('button', 'Launch').first()
                .as('launchButton')

            cy.get('@launchButton')
                .trigger('mousedown')
                .should('have.class', 'pressed')

            cy.get('@launchButton')
                .trigger('mouseup')
                .should('not.have.class', 'pressed')
        })

        it('should highlight nudge buttons when pressed', () => {
            cy.contains('button', /Nudge.*Left/i).first()
                .trigger('mousedown')
                .should('have.class', 'pressed')
                .trigger('mouseup')
                .should('not.have.class', 'pressed')

            cy.contains('button', /Nudge.*Right/i).first()
                .trigger('mousedown')
                .should('have.class', 'pressed')
                .trigger('mouseup')
                .should('not.have.class', 'pressed')
        })
    })

    describe('Dropdown Selections', () => {
        it('should allow model selection', () => {
            cy.contains('.control-group, .controls-container', 'Model')
                .find('select option')
                .then($options => {
                    if ($options.length > 1) {
                        const value = $options.eq(1).val()
                        cy.selectDropdown('Model', value)
                        cy.contains('.control-group, .controls-container', 'Model')
                            .find('select')
                            .should('have.value', value)
                    }
                })
        })

        it('should allow layout selection', () => {
            cy.contains('.control-group, .controls-container', 'Layout')
                .find('select option')
                .then($options => {
                    if ($options.length > 1) {
                        const value = $options.eq(1).val()
                        cy.selectDropdown('Layout', value)
                        cy.contains('.control-group, .controls-container', 'Layout')
                            .find('select')
                            .should('have.value', value)
                    }
                })
        })

        it('should allow camera preset (View) selection', () => {
            cy.contains('.control-group, .controls-container', 'View')
                .find('select option')
                .then($options => {
                    if ($options.length > 1) {
                        // Skip the first option if it's "Select Camera Preset"
                        const value = $options.eq(1).val()
                        if (value) {
                            cy.selectDropdown('View', value)
                            cy.contains('.control-group, .controls-container', 'View')
                                .find('select')
                                .should('have.value', value)
                        }
                    }
                })
        })

        it('should persist selected view on reload', () => {
            cy.contains('.control-group, .controls-container', 'View')
                .find('select option')
                .then($options => {
                    if ($options.length > 1) {
                        const value = $options.eq(1).val()
                        if (value) {
                            cy.selectDropdown('View', value)
                            cy.wait(500) // Wait for save
                            cy.reload()
                            cy.waitForConnection()
                            cy.contains('.control-group, .controls-container', 'View')
                                .find('select')
                                .should('have.value', value)
                        }
                    }
                })
        })
    })

    describe('Toggle Buttons', () => {
        it('should toggle AI on/off', () => {
            cy.contains('button', 'AI:')
                .as('aiToggle')

            // Get initial state
            cy.get('@aiToggle').then($btn => {
                const initialState = $btn.hasClass('active')

                // Click and verify state changed
                cy.get('@aiToggle').click()
                cy.wait(100)
                cy.get('@aiToggle').should(initialState ? 'not.have.class' : 'have.class', 'active')

                // Click again to restore
                cy.get('@aiToggle').click()
                cy.wait(100)
                cy.get('@aiToggle').should(initialState ? 'have.class' : 'not.have.class', 'active')
            })
        })

        it('should toggle Auto-Start on/off', () => {
            cy.contains('button', 'Auto-Start:')
                .as('autoStartToggle')

            // Get initial state
            cy.get('@autoStartToggle').then($btn => {
                const initialState = $btn.hasClass('active')

                // Click and verify state changed
                cy.get('@autoStartToggle').click()
                cy.wait(100)
                cy.get('@autoStartToggle').should(initialState ? 'not.have.class' : 'have.class', 'active')

                // Click again to restore
                cy.get('@autoStartToggle').click()
                cy.wait(100)
                cy.get('@autoStartToggle').should(initialState ? 'have.class' : 'not.have.class', 'active')
            })
        })
    })

    describe('Settings Panel', () => {
        it('should switch between tabs', () => {
            cy.get('.tabs .tab').first().click()
            cy.get('.tabs .tab').first().should('have.class', 'active')

            cy.get('.tabs .tab').eq(1).then($tab => {
                if ($tab.length) {
                    cy.wrap($tab).click()
                    cy.get('.tabs .tab').eq(1).should('have.class', 'active')
                }
            })
        })

        it('should have physics sliders', () => {
            cy.get('input[type="range"]').should('have.length.greaterThan', 0)
        })
    })
})
