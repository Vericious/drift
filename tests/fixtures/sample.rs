//! This is a module-level inner doc comment.
//! It applies to the entire module.
#![allow(unused)]

// External doc comment for the user struct.
/// Represents a user in the system.
/// Use this for creating new user accounts.
pub struct User {
    /// User's unique identifier
    id: u64,
    /// User's display name
    name: String,
    /// User's email address
    email: String,
}

impl User {
    //! Inner doc for User impl block.
    //! This is attached to the impl.

    /// Create a new user with the given name and email.
    pub fn new(name: String, email: String) -> Self {
        User {
            id: 0,
            name,
            email,
        }
    }

    /// Returns the user's display name.
    pub fn get_name(&self) -> &str {
        &self.name
    }
}

/// Represents a priority level.
pub enum Priority {
    /// Low priority
    Low,
    /// Medium priority
    Medium,
    /// High priority
    High,
}

/// A trait for serializable types.
pub trait Serializable {
    /// Serialize to a JSON string.
    fn to_json(&self) -> String;
}

impl Serializable for User {
    /*!! Inner doc inside impl for Serializable. !!*/

    fn to_json(&self) -> String {
        format!(r#"{{"id":{},"name":"{}","email":"{}"}}"#, self.id, self.name, self.email)
    }
}

/// Module-level function documentation.
pub fn helper_function(x: i32, y: i32) -> i32 {
    x + y
}

/// A private struct only used internally.
struct InternalState {
    value: i32,
}

/// Standalone function with no docs.
fn unchecked() -> bool {
    true
}

// Inner docs on a struct body
struct Config {
    /// Timeout in seconds
    timeout: u64,
}

mod inner {
    //! Inner module documentation.
    //! More details about the inner module.

    /// A function in the inner module.
    pub fn inner_helper() {}
}

// Trailing code after module
