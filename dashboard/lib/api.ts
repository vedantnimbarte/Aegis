// The Aegis API client.
//
// Split in two so the endpoint list stays readable: ./api-transport carries
// auth, the refresh-retry and the organization header; ./api-endpoints is the
// typed method surface. Everything is re-exported here, so callers keep
// importing from "@/lib/api".

export { ApiError, AuthExpiredError } from "./api-transport";
export { api } from "./api-endpoints";
