import { AnimatePresence, motion } from "framer-motion"
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from "lucide-react"

export type StepStatus = "pending" | "running" | "done" | "failed" | "cancelled"

/** Ícono animado de estado de un paso — compartido entre cualquier panel de
 *  progreso (job de scraping, pipeline de /api/analyze, etc.). */
export function StatusIcon({ status }: { status: StepStatus }) {
  const common = "size-4"
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={status}
        initial={{ opacity: 0, scale: 0.8, rotate: -10 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        exit={{ opacity: 0, scale: 0.8, rotate: 10 }}
        transition={{ duration: 0.2, ease: [0.2, 0.65, 0.3, 0.9] }}
        className="inline-flex"
      >
        {status === "done" && <CheckCircle2 className={common} style={{ color: "var(--pos)" }} />}
        {status === "running" && (
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, ease: "linear", repeat: Infinity }}
            className="inline-flex"
          >
            <CircleDotDashed className={common} style={{ color: "var(--primary)" }} />
          </motion.span>
        )}
        {status === "failed" && <CircleX className={common} style={{ color: "var(--neg)" }} />}
        {status === "cancelled" && <CircleAlert className={common} style={{ color: "var(--warn)" }} />}
        {status === "pending" && <Circle className={common} style={{ color: "var(--faint)" }} />}
      </motion.span>
    </AnimatePresence>
  )
}
