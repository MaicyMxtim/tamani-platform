// k6 load profile for the venue API: a realistic mix of searches and
// feed reads. BASE_URL decides whether this tests the public edge
// (rate-limited) or the in-cluster service (raw capacity).
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://tamani-api";

export const options = {
  stages: [
    { duration: "30s", target: Number(__ENV.VUS_LOW || 10) },
    { duration: "90s", target: Number(__ENV.VUS_HIGH || 60) },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<400"],
  },
};

const paths = [
  "/venues?vibe=drinks&limit=10",
  "/venues?vibe=coffee&limit=10",
  "/venues?area=lanes&limit=10",
  "/venues?band=under_5&limit=10",
  "/feed?limit=20",
  "/health/live",
];

export default function () {
  const res = http.get(`${BASE}${paths[Math.floor(Math.random() * paths.length)]}`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(Math.random() * 0.5);
}
