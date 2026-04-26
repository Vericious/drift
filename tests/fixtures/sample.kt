//! Sample Kotlin source file for extractor testing.
//! This file contains realistic Kotlin declarations.

// Data class for representing a user account.
data class User(
    val id: Long,
    val name: String,
    val email: String,
)

// Regular class with a companion object.
class Config {
    companion object {
        /// Default timeout in milliseconds.
        const val DEFAULT_TIMEOUT = 5000

        /// Creates a new Config instance.
        fun create(): Config = Config()
    }

    /// Timeout value in ms.
    var timeout: Long = DEFAULT_TIMEOUT
}

// Top-level function.
fun helper(x: Int, y: Int): Int = x + y

// Object declaration (singleton).
object Logger {
    /// Log an info message.
    fun info(message: String) {
        println("[INFO] $message")
    }

    /// Log an error message.
    fun error(message: String) {
        println("[ERROR] $message")
    }
}

// Sealed class for result types.
sealed class Result<out T> {
    data class Success<T>(val value: T) : Result<T>()
    data class Failure(val message: String) : Result<Nothing>()
}

// Extension function on User.
fun User.displayName(): String = "${this.name} (${this.email})"

// Interface definition.
interface Repository<T> {
    fun findAll(): List<T>
    fun findById(id: Long): T?
    suspend fun save(entity: T): Boolean
}

// Abstract class.
abstract class BaseService {
    abstract fun process()

    /// Hook called before processing.
    protected open fun beforeProcess() {}

    /// Hook called after processing.
    protected open afterProcess() {}
}

// Inner class example.
class Outer {
    val value: Int = 42

    inner class Inner {
        fun getOuterValue(): Int = this@Outer.value
    }
}

// Enum class.
enum class Priority {
    LOW,
    MEDIUM,
    HIGH;

    fun label(): String = name.lowercase().replaceFirstChar { it.uppercase() }
}
