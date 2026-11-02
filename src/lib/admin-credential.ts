import { z } from "zod";

export const adminPassword = z.string().min(12).max(256);