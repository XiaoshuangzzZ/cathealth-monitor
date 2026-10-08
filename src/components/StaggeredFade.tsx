import { motion, useInView, type Variants } from 'framer-motion'
import { useRef } from 'react'

type StaggeredFadeProps = {
  text: string
  className?: string
}

const characterVariants: Variants = {
  hidden: {
    opacity: 0,
  },
  show: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.62,
      delay: index * 0.07,
      ease: 'easeOut',
    },
  }),
}

export function StaggeredFade({ text, className }: StaggeredFadeProps) {
  const lineRef = useRef<HTMLSpanElement>(null)
  const isInView = useInView(lineRef, { once: true, amount: 0.65 })

  return (
    <span ref={lineRef} className={className} aria-label={text}>
      {Array.from(text).map((character, index) => (
        <motion.span
          key={`${character}-${index}`}
          aria-hidden="true"
          className="inline-block"
          variants={characterVariants}
          custom={index}
          initial="hidden"
          animate={isInView ? 'show' : 'hidden'}
        >
          {character === ' ' ? '\u00a0' : character}
        </motion.span>
      ))}
    </span>
  )
}
