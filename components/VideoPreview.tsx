'use client'

import { AdGeneration } from '@/types'
import { useState } from 'react'

interface VideoPreviewProps {
  adGeneration: AdGeneration
}

export default function VideoPreview({ adGeneration }: VideoPreviewProps) {
  const [selectedClip, setSelectedClip] = useState<number | null>(null)

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Video Preview</h2>
      
      {adGeneration.final_video_url ? (
        <div className="space-y-6">
          <div className="bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '9/16', maxWidth: '405px', margin: '0 auto' }}>
            <video
              src={`http://localhost:8000${adGeneration.final_video_url}`}
              controls
              className="w-full h-full"
            >
              Your browser does not support the video tag.
            </video>
          </div>
          
          <div className="text-center">
            <a
              href={`http://localhost:8000${adGeneration.final_video_url}`}
              download
              className="inline-block px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Download Video
            </a>
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-xl text-gray-700">Assembling final video...</p>
        </div>
      )}

      {adGeneration.clips && adGeneration.clips.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold mb-4 text-gray-800">Individual Clips</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {adGeneration.clips.map((clip) => (
              <div
                key={clip.id}
                className={`border-2 rounded-lg overflow-hidden cursor-pointer transition-all ${
                  selectedClip === clip.sequence_index
                    ? 'border-indigo-600 ring-2 ring-indigo-300'
                    : 'border-gray-200 hover:border-indigo-400'
                }`}
                onClick={() => setSelectedClip(clip.sequence_index)}
                style={{ aspectRatio: '9/16' }}
              >
                {clip.local_path || clip.s3_url ? (
                  <video
                    src={clip.local_path ? `http://localhost:8000/api/files/${clip.local_path.split('/').pop()}` : clip.s3_url}
                    className="w-full h-full object-cover"
                    muted
                    playsInline
                  />
                ) : (
                  <div className="w-full h-full bg-gray-100 flex items-center justify-center">
                    <span className="text-gray-400 text-sm">Clip {clip.sequence_index}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

