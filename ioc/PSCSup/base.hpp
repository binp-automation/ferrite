#pragma once

#include <dbCommon.h>
#include <dbAccess.h>
#include <callback.h>

// A non-owning wrapper around EPICS record.
template <
    typename RawRecord,
    typename FinalHandler
>
class EpicsRecord : public virtual Record {
protected:
    struct PrivateData {
        std::unique_ptr<FinalHandler> handler;
        std::optional<epicsCallback> async_callback_data;
    };

private:
    RawRecord &raw_;

public:
    explicit EpicsRecord(RawRecord &raw);
    virtual ~EpicsRecord() = default;

    // Record is non-copyable and non-movable.
    EpicsRecord(const EpicsRecord &) = delete;
    EpicsRecord &operator=(const EpicsRecord &) = delete;

protected:
    virtual void process_sync() = 0;

private:
    void set_private_data(std::unique_ptr<PrivateData> &&data) {
        raw_common().dpvt = static_cast<void *>(data.release());
    }
    const PrivateData &private_data() const {
        return *static_cast<const PrivateData *>(raw_common().dpvt);
    }
    PrivateData &private_data() {
        return *static_cast<PrivateData *>(raw_common().dpvt);
    }

    bool is_process_active() const {
        return raw_common().pact != FALSE;
    }
    void set_process_active(bool pact) {
        raw_common().pact = pact ? TRUE : FALSE;
    }

    [[nodiscard]]
    ScanLockGuard scan_lock() {
        return ScanLockGuard(raw_common());
    }

    void Record::notify_async_process_complete() {
        auto rset = static_cast<struct typed_rset *>(raw_common().rset);
        (*rset->process)(raw());
    }

    void Record::schedule_async_process() {
        if (private_data().async_callback_data.has_value()) {
            callbackRequest(&*private_data().async_callback_data);
        }
    }

    void process_async() {
        const auto guard = record.scan_lock();
        process_sync();
        notify_async_process_complete();
    }

    [[nodiscard]]
    epicsCallback make_async_process_callback() {
        epicsCallback callback;

        callbackSetCallback(&[](epicsCallback *self) {
            static_cast<EpicsRecord *>(self->user)->process_async();
        }, &callback);
        callbackSetUser(static_cast<void *>(this), &callback);
        callbackSetPriority(priorityLow, &callback);

        return callback;
    }

public:
    const RawRecord &raw() const {
        return raw_;
    }
    RawRecord &raw() {
        return raw_;
    }
    const dbCommon &raw_common() const {
        return static_cast<const dbCommon &>(raw());
    }
    dbCommon &raw_common() {
        return static_cast<dbCommon &>(raw());
    }

    void initialize() {
        set_private_data(std::make_unique<PrivateData>());
    }

    void set_handler() {
        if (handler.is_async()) {
            private_data().async_callback_data = make_async_process_callback();
        }
        private_data().handler = std::move(handler);
    }

    const FinalHandler &handler() const {
        return *private_data().handler;
    }
    FinalHandler &handler() {
        return *private_data().handler;
    }

    void process() {
        if (private_data().async_callback_data.has_value()) {
            if (!is_process_active()) {
                set_process_active(true);
                schedule_async_process();
            } else {
                set_process_active(false);
            }
        } else {
            process_sync();
        }
    }

public:
    virtual std::string_view name() const override {
        return std::string_view(raw_common().name);
    }
};
