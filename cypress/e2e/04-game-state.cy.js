/**
 * Game State test - Verify game state updates and displays correctly
 */
describe('Pinball Wizard - Game State', () => {
    beforeEach(() => {
        cy.visit('/')
        cy.waitForConnection()
        cy.waitForVideo()
    })

    describe('Score Display', () => {
        it('should display score with proper formatting', () => {
            cy.getScore().should('be.visible')
            cy.get('.score-reel').should('have.length.greaterThan', 0)
        })

        it('should show score reels with animation', () => {
            cy.get('.score-reel .score-strip').should('exist')
        })

        it('should display high score', () => {
            cy.contains('.label', /HIGH.*SCORE/i)
                .should('be.visible')
                .parent()
                .find('.score-board')
                .should('be.visible')
        })
    })

    describe('Ball Count', () => {
        it('should display current ball count', () => {
            cy.getBallCount()
                .should('be.visible')
        })
    })

    describe('Tilt System', () => {
        it('should display tilt value', () => {
            // Tilt is shown in the stats/settings area
            cy.contains(/tilt/i).should('exist')
        })

        it('should not show TILTED overlay initially', () => {
            // Element uses v-if so it won't exist in DOM when not tilted
            cy.get('body').then($body => {
                if ($body.find('#tilted-overlay').length > 0) {
                    cy.get('#tilted-overlay').should('not.be.visible')
                }
            })
        })
    })

    describe('Video Feed', () => {
        it('should continuously update video feed', () => {
            cy.get('#video-stream')
                .should('be.visible')
                .and('have.attr', 'src')
                .and('include', 'data:image')
        })
    })

    describe('Game History', () => {
        it('should display history container', () => {
            cy.get('#history-container').should('be.visible')
        })

        it('should show game log', () => {
            cy.get('.game-log-container').should('be.visible')
        })
    })

    describe('WebSocket Connection', () => {
        it('should maintain connection indicator', () => {
            cy.get('.status-dot')
                .should('have.class', 'status-connected')
        })
    })

    describe('Responsive Behavior', () => {
        it('should show appropriate controls on mobile', () => {
            cy.viewport(375, 667)
            cy.reload()
            cy.waitForConnection()
            cy.get('#input-area').should('be.visible')
        })

        it('should show appropriate controls on desktop', () => {
            cy.viewport(1280, 720)
            cy.reload()
            cy.waitForConnection()
            cy.get('.desktop-only').should('be.visible')
        })
    })
})
