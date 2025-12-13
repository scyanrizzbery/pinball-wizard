import io from 'socket.io-client'

const sockets = {
    game: io('/game'),
    control: io('/control'),
    config: io('/config'),
    training: io('/training')
}

export default sockets
