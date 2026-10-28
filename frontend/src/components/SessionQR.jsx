import { QRCodeSVG } from 'qrcode.react'

export default function SessionQR({ code, baseUrl }) {
  const url = `${baseUrl || window.location.origin}/join/${code}`
  return (
    <div className="inline-block rounded-xl bg-white p-3 shadow">
      <QRCodeSVG value={url} size={220} />
    </div>
  )
}
