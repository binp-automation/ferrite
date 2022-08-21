use crate::raw;
use std::any::TypeId;

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub enum Direction {
    Read,
    Write,
}

impl Direction {
    pub(crate) fn from_raw(raw_dir: raw::var::Dir) -> Self {
        match raw_dir {
            raw::var::Dir::Read => Direction::Read,
            raw::var::Dir::Write => Direction::Write,
        }
    }
}

/// Type of scalars.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub enum ScalarType {
    /// Integer type.
    ///
    /// Parameters:
    /// + `width` - width in bytes. Supported values: 1, 2, 4, 8.
    /// + `signed` - signedness.
    Int { width: u8, signed: bool },
    /// Floating-point type.
    ///
    /// Parameters:
    /// + `width` - width of the type in bytes. Supported values: 4 and 8.
    Float { width: u8 },
    /// Unknown type.
    Unknown,
}

impl ScalarType {
    pub(crate) fn from_raw(raw_scal_type: raw::var::ScalarType) -> Self {
        match raw_scal_type {
            raw::var::ScalarType::None => ScalarType::Unknown,
            raw::var::ScalarType::U8 => ScalarType::Int {
                width: 1,
                signed: false,
            },
            raw::var::ScalarType::I8 => ScalarType::Int {
                width: 1,
                signed: true,
            },
            raw::var::ScalarType::U16 => ScalarType::Int {
                width: 2,
                signed: false,
            },
            raw::var::ScalarType::I16 => ScalarType::Int {
                width: 2,
                signed: true,
            },
            raw::var::ScalarType::U32 => ScalarType::Int {
                width: 4,
                signed: false,
            },
            raw::var::ScalarType::I32 => ScalarType::Int {
                width: 4,
                signed: true,
            },
            raw::var::ScalarType::U64 => ScalarType::Int {
                width: 8,
                signed: false,
            },
            raw::var::ScalarType::I64 => ScalarType::Int {
                width: 8,
                signed: true,
            },
            raw::var::ScalarType::F32 => ScalarType::Float { width: 4 },
            raw::var::ScalarType::F64 => ScalarType::Float { width: 8 },
        }
    }

    pub fn type_id(self) -> Option<TypeId> {
        match self {
            ScalarType::Int { width, signed } => match (width, signed) {
                (1, false) => Some(TypeId::of::<u8>()),
                (1, true) => Some(TypeId::of::<i8>()),
                (2, false) => Some(TypeId::of::<u16>()),
                (2, true) => Some(TypeId::of::<i16>()),
                (4, false) => Some(TypeId::of::<u32>()),
                (4, true) => Some(TypeId::of::<i32>()),
                (8, false) => Some(TypeId::of::<u64>()),
                (8, true) => Some(TypeId::of::<i64>()),
                _ => None,
            },
            ScalarType::Float { width } => match width {
                4 => Some(TypeId::of::<f32>()),
                8 => Some(TypeId::of::<f64>()),
                _ => None,
            },
            ScalarType::Unknown => None,
        }
    }
}

/// Type of the variable.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub enum VariableType {
    Scalar {
        scal_type: ScalarType,
    },
    Array {
        scal_type: ScalarType,
        max_len: usize,
    },
    Unknown,
}

impl VariableType {
    pub(crate) fn from_raw(raw_type: raw::var::Type) -> Self {
        match raw_type.kind {
            raw::var::Kind::Scalar => VariableType::Scalar {
                scal_type: ScalarType::from_raw(raw_type.scalar_type),
            },
            raw::var::Kind::Array => VariableType::Array {
                scal_type: ScalarType::from_raw(raw_type.scalar_type),
                max_len: raw_type.array_max_len,
            },
        }
    }
}
