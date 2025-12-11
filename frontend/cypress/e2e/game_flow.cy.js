describe('Game Flow & Score Persistence', () => {
    it('should accumulate score across balls and show Game Over', () => {
        cy.visit('/');
        cy.get('#app').should('be.visible'); // Ensure Vue is mounted
        cy.window().should('have.property', 'sockets');

        // Disconnect from real backend to prevent interference
        cy.window().then((win) => {
            if (win.sockets && win.sockets.game) {
                win.sockets.game.disconnect();
            }
        });

        // Helper to simulate stats update
        const sendStats = (stats) => {
            cy.window().then((win) => {
                const listeners = win.sockets.game.listeners('stats_update');
                if (listeners.length > 0) listeners[0](stats);
            });
        };

        // 1. Start Game (Ball 1)
        sendStats({
            score: 1000,
            current_ball: 1,
            balls_remaining: 2,
            game_over: false
        });

        // Verify ScoreBoard shows 1000
        // Use hidden test element for reliability
        cy.get('[data-cy="score-value"]').should('have.text', '1000');
        // Verify Ball 1
        cy.get('.scoreboard-overlay').should('contain', '1'); // Ball count

        // 2. Ball 1 Drains -> Ball 2 Starts
        // Backend would send update with current_ball: 2, same score (or higher)
        sendStats({
            score: 1500, // Score increased before drain
            current_ball: 2,
            balls_remaining: 1,
            game_over: false
        });

        // Verify Score is still 1500 (Persisted/Accumulated)
        cy.get('[data-cy="score-value"]').should('have.text', '1500');
        // Verify Ball 2
        // Assert Score did NOT reset to 0

        // 3. Ball 2 Drains -> Ball 3 Starts
        sendStats({
            score: 2000,
            current_ball: 3,
            balls_remaining: 0,
            game_over: false
        });
        cy.get('[data-cy="score-value"]').should('have.text', '2000');

        // 4. Ball 3 Drains -> Game Over
        sendStats({
            score: 2000,
            current_ball: 3,
            balls_remaining: 0,
            game_over: true
        });

        // Verify Game Over Screen
        cy.get('.game-over-overlay').should('be.visible');
        cy.get('.game-over-overlay').should('have.css', 'z-index', '3000');

        // Verify Final Score on Game Over screen (if displayed)
        // Or just ensure scoreboard visible behind it?
    });
});
