/**
 * UI Elements test - Verify all UI elements are present and styled correctly
 */
describe('Pinball Wizard - UI Elements', () => {
    beforeEach(() => {
        cy.visit('/')
        cy.waitForConnection()
    })

    describe('Header and Title', () => {
        it('should display the application title', () => {
            cy.get('h1').should('contain', 'Pinball Wizard')
        })

        it('should show connection status', () => {
            cy.get('.connection-status').should('be.visible')
            cy.get('.status-dot').should('have.class', 'status-connected')
        })
    })

    describe('Game Display', () => {
        it('should display video feed', () => {
            // Ensure we are in video mode
            cy.get('body').then(($body) => {
                if ($body.find('button:contains("Switch to 2D")').length > 0) {
                    cy.contains('button', 'Switch to 2D').click()
                }
            })
            cy.get('#video-stream').should('be.visible')
        })

        it('should show score display', () => {
            cy.get('.score-board').should('be.visible')
            cy.get('.score-reel').should('have.length.greaterThan', 0)
        })

        it('should display stats', () => {
            cy.getScore().should('be.visible')
            cy.getBallCount().should('be.visible')
            cy.contains('.label', /HIGH.*SCORE/i).should('be.visible')
        })
    })

    describe('Control Buttons', () => {
        it('should display flipper buttons', () => {
            cy.contains('button', /Left/i).should('be.visible')
            cy.contains('button', /Right/i).should('be.visible')
        })

        it('should display launch button', () => {
            cy.contains('button', 'Launch').should('be.visible')
        })

        it('should display nudge buttons', () => {
            cy.contains('button', /Nudge.*L/i).should('be.visible')
            cy.contains('button', /Nudge.*R/i).should('be.visible')
        })

        it('should have properly styled circular launch button on desktop', () => {
            cy.viewport(1280, 720)
            cy.reload()
            cy.waitForConnection()
            cy.contains('button.desktop-only', 'Launch')
                .should('have.css', 'border-radius', '50%')
        })
    })

    describe('Dropdowns', () => {
        it('should display Model dropdown', () => {
            cy.contains('Model')
                .parent()
                .find('select')
                .should('be.visible')
        })

        it('should display Layout dropdown', () => {
            cy.contains('Layout')
                .parent()
                .find('select')
                .should('be.visible')
        })

        it('should display View (camera preset) dropdown', () => {
            cy.contains('View')
                .parent()
                .find('select')
                .should('be.visible')
        })
    })

    describe('Toggle Buttons', () => {
        it('should display AI toggle', () => {
            cy.contains('button', 'AI:').should('be.visible')
        })

        it('should display Auto-Start toggle', () => {
            cy.contains('button', 'Auto-Start:').should('be.visible')
        })
    })

    describe('Settings Panel', () => {
        beforeEach(() => {
            // Ensure we are in 3D mode (Settings are inside Pinball3D)
            cy.get('body').then(($body) => {
                // If we see "Switch to 3D", we are in 2D mode -> click it
                if ($body.find('button:contains("Switch to 3D")').length > 0) {
                    cy.contains('button', 'Switch to 3D').click()
                }
            })
            // Wait for 3D view to load
            cy.get('.sound-toggle-btn').should('be.visible').click()
        })

        it('should have tabs', () => {
            cy.get('.tabs .tab').should('have.length.greaterThan', 0)
        })

        it('should display physics sliders', () => {
            cy.get('input[type="range"]').should('have.length.greaterThan', 0)
        })
    })

    describe('Game History', () => {
        it('should display history container', () => {
            cy.get('#history-container').should('be.visible')
            cy.contains('h3', 'Game History').should('be.visible')
        })
    })

    describe('Responsive Design', () => {
        it('should show mobile buttons on small viewport', () => {
            cy.viewport(375, 667)
            cy.reload()
            cy.waitForConnection()
            cy.get('#input-area').should('be.visible')
        })

        it('should show desktop buttons on large viewport', () => {
            cy.viewport(1280, 720)
            cy.reload()
            cy.waitForConnection()
            cy.get('.desktop-only').should('be.visible')
        })
    })
})
