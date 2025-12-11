describe('Game Over Screen', () => {
    it('should display the game over overlay when game_over is triggered', () => {
        // Visit the app
        cy.visit('/');
        cy.get('#app').should('be.visible'); // Ensure Vue is mounted

        // Wait for app to be ready and socket to be connected
        cy.window().should('have.property', 'sockets');

        // Simulate Game Over Event via Sockets
        cy.window().then((win) => {
            const statsData = {
                game_over: true,
                score: 1337,
                last_score: 1337, // Displayed score
                current_ball: 3,
                balls_remaining: 0
            };

            // Trigger the stats_update listener directly
            // Client-side socket: calling 'onevent' or finding listeners
            // socket.listeners("stats_update") returns array of functions
            const listeners = win.sockets.game.listeners('stats_update');
            expect(listeners.length).to.be.greaterThan(0);

            // Call the listener to simulate server message
            listeners[0](statsData);
        });

        // Assert Overlay Visibility
        // .game-over-overlay should be visible
        cy.get('.game-over-overlay').should('be.visible');
        cy.get('.game-over-overlay h1').should('contain', 'GAME OVER'); // Check header
        // Check formatted score (1,337)
        cy.get('.final-score').should('contain', '1,337');
    });

    it('should have correct z-index', () => {
        cy.visit('/');
        // Trigger it again
        cy.window().then((win) => {
            win.sockets.game.listeners('stats_update')[0]({ game_over: true });
        });

        cy.get('.game-over-overlay')
            .should('have.css', 'z-index', '3000');
    });
});
