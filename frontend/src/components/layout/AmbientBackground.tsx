export function AmbientBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-[#47dbcf]/10 blur-[120px]" />
      <div className="absolute -right-40 top-1/3 h-[500px] w-[500px] rounded-full bg-[#ba98ff]/10 blur-[140px]" />
      <div className="absolute bottom-10 left-1/3 h-80 w-80 rounded-full bg-[#ffca45]/5 blur-[100px]" />
    </div>
  )
}
