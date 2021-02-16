#include "zmq.hpp"

#include <iostream>
#include <core/assert.hpp>


namespace zmq_helper {

void ContextDestroyer::operator()(void *context) const {
    assert_eq(zmq_ctx_destroy(context), 0);
}
void SocketCloser::operator()(void *socket) const {
    assert_eq(zmq_close(socket), 0);
}

static const ContextDestroyer CONTEXT_DESTROYER{};
static const SocketCloser SOCKET_CLOSER{};

ContextGuard guard_context(void *context) {
    return ContextGuard(context, CONTEXT_DESTROYER);
}
SocketGuard guard_socket(void *socket) {
    return SocketGuard(socket, SOCKET_CLOSER);
}

} // namespace zmq_helper

Result<ZmqChannel, ZmqChannel::Error> ZmqChannel::create(const std::string &host) {
    void *raw_context = zmq_ctx_new();
    if (raw_context == nullptr) {
        return Err(Error{ErrorKind::IoError, "Cannot create ZMQ context"});
    }
    auto context = zmq_helper::guard_context(raw_context);

    void *raw_socket = zmq_socket(context.get(), ZMQ_PAIR);
    if (raw_socket == nullptr) {
        return Err(Error{ErrorKind::IoError, "Cannot create ZMQ socket"});
    }
    auto socket = zmq_helper::guard_socket(raw_socket);

    if (zmq_connect(socket.get(), host.c_str()) != 0) {
        return Err(Error{ErrorKind::IoError, "Error connecting ZMQ socket"});
    }
    std::cout << "[app] ZMQ connected to " << host << std::endl;

    return Ok(ZmqChannel(host, std::move(context), std::move(socket)));
}

Result<std::monostate, ZmqChannel::Error> ZmqChannel::send(
    const uint8_t *bytes, size_t length, std::optional<std::chrono::milliseconds> timeout
) {
    zmq_pollitem_t pollitem = {this->socket_.get(), 0, ZMQ_POLLOUT, 0};
    // Handle timeout error separately
    std::cout << "[app] ZMQ polling send ..." << std::endl;
    if (!timeout || zmq_poll(&pollitem, 1, timeout->count()) > 0) {
        std::cout << "[app] ZMQ sending ..." << std::endl;
        if (zmq_send(this->socket_.get(), bytes, length, !timeout ? 0 : ZMQ_NOBLOCK) <= 0) {
            return Err(Error{ErrorKind::IoError, "Error send"});
        }
        std::cout << "[app] ZMQ sent " << length << " bytes" << std::endl;
        return Ok(std::monostate{});
    } else {
        return Err(Error{ErrorKind::TimedOut, "Timed out send"});
    }
}
Result<size_t, ZmqChannel::Error> ZmqChannel::receive(
    uint8_t *bytes, size_t max_length, std::optional<std::chrono::milliseconds> timeout
) {
    zmq_pollitem_t pollitem = {this->socket_.get(), 0, ZMQ_POLLIN, 0};
    // Handle timeout error separately
    std::cout << "[app] ZMQ polling recv ..." << std::endl;
    if (!timeout || zmq_poll(&pollitem, 1, timeout->count()) > 0) {
        std::cout << "[app] ZMQ receiving ..." << std::endl;
        int ret = zmq_recv(this->socket_.get(), bytes, max_length, !timeout ? 0 : ZMQ_NOBLOCK);
        if (ret <= 0) {
            return Err(Error{ErrorKind::IoError, "Error receive"});
        }
        std::cout << "[app] ZMQ received " << ret << " bytes" << std::endl;
        return Ok<size_t>(ret);
    } else {
        return Err(Error{ErrorKind::TimedOut, "Timed out receive"});
    }
}
