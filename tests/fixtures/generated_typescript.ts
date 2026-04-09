/**
 * Generated TypeScript fixture for testing extractors
 */

export interface User {
  /** User's full name */
  name: string;
  /** User's email address */
  email: string;
  /** User's age in years */
  age?: number;
  /** Whether user is active */
  active: boolean;
}

export interface Config {
  /** API endpoint URL */
  apiUrl: string;
  /** API key (read-only after initialization) */
  readonly apiKey: string;
  /** Timeout in milliseconds */
  timeout?: number;
}

export enum UserRole {
  Admin = "ADMIN",
  User = "USER",
  Guest = "GUEST",
}

export enum HttpStatus {
  Ok = 200,
  NotFound = 404,
  Error = 500,
}

export type UserOrGuest = User | { guest: true; name: string };

export function greet(name: string, greeting: string = "Hello"): string {
  return `${greeting}, ${name}!`;
}

export async function fetchData<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}
