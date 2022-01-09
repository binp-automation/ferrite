#pragma once

#include <string>
#include <memory>

#include <zmq.h>

#include "base.hpp"

namespace zmq_helper {

struct ContextDestroyer final {
    void operator()(void *context) const;
};
using ContextGuard = std::unique_ptr<void, ContextDestroyer>;
ContextGuard guard_context(void *context);

struct SocketCloser final {
    void operator()(void *socket) const;
};
using SocketGuard = std::unique_ptr<void, SocketCloser>;
SocketGuard guard_socket(void *socket);

template <typename T>
inline int64_t duration_to_microseconds(const T duration) {
    return std::chrono::duration_cast<std::chrono::microseconds>(duration).count();
}

} // namespace zmq_helper

class ZmqChannel final : public Channel {
private:
    std::string host_;
    zmq_helper::ContextGuard context_;
    zmq_helper::SocketGuard socket_;

    inline ZmqChannel(
        const std::string &host,
        zmq_helper::ContextGuard &&context,
        zmq_helper::SocketGuard &&socket,
        size_t max_len
    ) :
        Channel(max_len),
        host_(host),
        context_(std::move(context)),
        socket_(std::move(socket))
    {}

public:
    virtual ~ZmqChannel() override = default;

    ZmqChannel(ZmqChannel &&) = default;
    ZmqChannel &operator=(ZmqChannel &&) = default;

    static Result<ZmqChannel, Error> create(const std::string &host, size_t max_length);

    virtual Result<std::monostate, Error> send_raw(const uint8_t *bytes, size_t length, std::optional<std::chrono::milliseconds> timeout) override;
    virtual Result<size_t, Error> receive_raw(uint8_t *bytes, size_t max_length, std::optional<std::chrono::milliseconds> timeout) override;
};
