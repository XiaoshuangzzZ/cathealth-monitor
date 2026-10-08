import { motion } from 'framer-motion'
import { useState } from 'react'
import { StaggeredFade } from './components/StaggeredFade'

const entranceTransition = {
  duration: 0.8,
  ease: 'easeOut' as const,
}

function App() {
  const [isExperienceActive, setIsExperienceActive] = useState(false)

  return (
    <main className={`hero-shell ${isExperienceActive ? 'realm-awake' : ''}`}>
      <div className="ambient ambient-lens" aria-hidden="true" />
      <div className="ambient ambient-tide" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      <section
        className="relative z-10 flex min-h-screen flex-col items-center justify-center px-5 pt-12 text-center sm:px-8 sm:pt-16 md:pt-24"
        aria-labelledby="hidden-realm-title"
      >
        <div className="flex w-full max-w-7xl flex-col items-center">
          <p className="mb-7 font-sans text-[0.61rem] font-medium uppercase tracking-[0.32em] text-white/40 sm:mb-9 sm:text-[0.67rem]">
            An observation in slow light
          </p>

          <h1
            id="hidden-realm-title"
            className="font-garamond mb-6 text-4xl font-normal leading-[1.08] tracking-tight text-white sm:mb-8 sm:text-6xl md:text-8xl lg:text-9xl"
          >
            <StaggeredFade text="WITNESS THE" className="block" />
            <StaggeredFade text="HIDDEN REALM" className="block" />
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...entranceTransition, delay: 1.6 }}
            className="mb-8 max-w-xs font-sans text-sm font-light leading-relaxed text-white/70 sm:mb-10 sm:max-w-md sm:text-base md:text-lg"
          >
            <span className="whitespace-nowrap">An odyssey through delicate living forms,</span>{' '}
            <br className="hidden sm:block" />
            <span>revealed by lens and curiosity.</span>
          </motion.p>

          <motion.button
            type="button"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...entranceTransition, delay: 2.0 }}
            className="liquid-glass rounded-full px-7 py-3.5 font-sans text-[0.68rem] font-medium uppercase tracking-[0.18em] text-white/90 sm:px-10 sm:py-4 sm:text-xs sm:tracking-[0.2em]"
            onClick={() => setIsExperienceActive(true)}
            aria-describedby="experience-status"
          >
            <span className="relative z-10">Begin the Experience</span>
          </motion.button>
          <span id="experience-status" className="sr-only" aria-live="polite">
            {isExperienceActive ? 'The hidden realm is now in focus.' : ''}
          </span>
        </div>
      </section>
    </main>
  )
}

export default App
