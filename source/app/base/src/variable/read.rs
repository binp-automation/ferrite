use crate::raw;
use std::{
    future::Future,
    marker::PhantomData,
    mem::drop,
    pin::Pin,
    task::{Context, Poll},
};

pub struct ReadVariable<T: Copy> {
    raw: raw::Variable,
    _phantom: PhantomData<T>,
}

impl<T: Copy> ReadVariable<T> {
    pub(crate) fn from_raw(raw: raw::Variable) -> Self {
        Self {
            raw,
            _phantom: PhantomData,
        }
    }

    pub fn read(&mut self) -> ReadFuture<'_, T> {
        ReadFuture {
            owner: self,
            complete: false,
        }
    }
}

pub struct ReadFuture<'a, T: Copy> {
    owner: &'a mut ReadVariable<T>,
    complete: bool,
}

impl<'a, T: Copy> Unpin for ReadFuture<'a, T> {}

impl<'a, T: Copy> Future for ReadFuture<'a, T> {
    type Output = T;

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<T> {
        assert!(!self.complete);
        let mut guard = self.owner.raw.lock_mut();
        let ps = guard.proc_state();
        if !ps.processing {
            ps.set_waker(cx.waker());
            unsafe { guard.request_proc() };
            return Poll::Pending;
        }
        let val = unsafe { *(guard.data_ptr() as *const T) };
        unsafe { guard.complete_proc() };
        drop(guard);
        self.complete = true;
        Poll::Ready(val)
    }
}

impl<'a, T: Copy> Drop for ReadFuture<'a, T> {
    fn drop(&mut self) {
        let guard = self.owner.raw.lock();
        if !self.complete {
            guard.proc_state().clean_waker();
        }
    }
}
