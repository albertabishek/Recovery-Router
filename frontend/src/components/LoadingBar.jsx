import { createContext, useContext, useState, useCallback, useRef } from 'react'

const LoadingContext = createContext()

export function useLoading() {
  return useContext(LoadingContext)
}

export function LoadingProvider({ children }) {
  const [active, setActive] = useState(false)
  const countRef = useRef(0)

  const start = useCallback(() => {
    countRef.current += 1
    setActive(true)
  }, [])

  const done = useCallback(() => {
    countRef.current = Math.max(0, countRef.current - 1)
    if (countRef.current === 0) setActive(false)
  }, [])

  return (
    <LoadingContext.Provider value={{ start, done }}>
      <LoadingBar active={active} />
      {children}
    </LoadingContext.Provider>
  )
}

function LoadingBar({ active }) {
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, height: 3,
      zIndex: 9999, pointerEvents: 'none',
      opacity: active ? 1 : 0,
      transition: active ? 'none' : 'opacity 0.4s ease 0.1s',
    }}>
      <div style={{
        height: '100%',
        background: 'linear-gradient(90deg, #528FF0, #36b3f0, #528FF0)',
        backgroundSize: '300% 100%',
        animation: active ? 'loadingBar 1.5s ease-in-out infinite, loadingGrow 8s ease-out forwards' : 'none',
        borderRadius: '0 2px 2px 0',
      }} />
      <style>{`
        @keyframes loadingBar {
          0% { background-position: 100% 0; }
          100% { background-position: -100% 0; }
        }
        @keyframes loadingGrow {
          0% { width: 0%; }
          10% { width: 30%; }
          50% { width: 70%; }
          80% { width: 85%; }
          100% { width: 95%; }
        }
      `}</style>
    </div>
  )
}
