'use client'

import { AdGeneration } from '@/types'
import { useState, useEffect } from 'react'

interface VideoPreviewProps {
  adGeneration: AdGeneration
}

export default function VideoPreview({ adGeneration }: VideoPreviewProps) {
  const [progress, setProgress] = useState(0)

  // Calculate progress based on clips
  useEffect(() => {
    if (adGeneration.status === 'completed') {
      setProgress(100)
    } else if (adGeneration.clips && adGeneration.clips.length > 0) {
      const completedCount = adGeneration.clips.filter((c: any) => c.status === 'completed').length
      const totalClips = adGeneration.clips.length || 12 // Default to 12 if not set
      const calculatedProgress = Math.round((completedCount / totalClips) * 100)
      setProgress(calculatedProgress)
    } else {
      setProgress(5) // Start at 5% if processing but no clips yet
    }
  }, [adGeneration])

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Video Generation</h2>
      
      {/* Progress Section */}
      {adGeneration.status !== 'completed' && adGeneration.status !== 'failed' && (
        <div className="mb-8">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Generating Scenes...</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
             <div 
               className="bg-indigo-600 h-full transition-all duration-500 ease-out"
               style={{ width: `${progress}%` }}
             ></div>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-2">
            {adGeneration.clips?.map((clip: any, idx: number) => (
               <div key={idx} className={`h-1.5 rounded-full ${
                 clip.status === 'completed' ? 'bg-green-500' : 
                 clip.status === 'generating' ? 'bg-indigo-400 animate-pulse' : 'bg-gray-200'
               }`} />
            ))}
          </div>
          <p className="text-center text-sm text-gray-500 mt-4">
            This may take 3-5 minutes. Please don't close this tab.
          </p>
        </div>
      )}

      {/* Video Player */}
      {adGeneration.final_video_url ? (
        <div className="space-y-6">
          <div className="bg-black rounded-lg overflow-hidden border-4 border-gray-900 shadow-2xl" style={{ aspectRatio: '9/16', maxWidth: '360px', margin: '0 auto' }}>
            <video
              src={`http://localhost:8000${adGeneration.final_video_url}`}
              controls
              autoPlay
              loop
              className="w-full h-full object-cover"
            >
              Your browser does not support the video tag.
            </video>
          </div>
          
          <div className="text-center">
            <a
              href={`http://localhost:8000${adGeneration.final_video_url}`}
              download
              className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Download Video
            </a>
          </div>
        </div>
      ) : adGeneration.status === 'failed' ? (
        <div className="text-center text-red-600 p-4 bg-red-50 rounded-lg">
          <p>Generation failed. Please try again.</p>
        </div>
      ) : null}
    </div>
  )
}