'use client'

import { AdGeneration } from '@/types'
import { useState, useEffect } from 'react'

interface VideoPreviewProps {
  adGeneration: AdGeneration
}

export default function VideoPreview({ adGeneration }: VideoPreviewProps) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (adGeneration.status === 'completed') {
      setProgress(100)
    } else if (adGeneration.clips && adGeneration.clips.length > 0) {
      const completedCount = adGeneration.clips.filter((c: any) => c.status === 'completed').length
      const totalClips = adGeneration.clips.length
      
      // Calculate progress based on clips (0-90%)
      const clipProgress = totalClips > 0 ? (completedCount / totalClips) * 90 : 0
      
      // Add a little extra if currently assembling
      const assembleProgress = adGeneration.status === 'assembling' ? 5 : 0
      
      setProgress(Math.round(clipProgress + assembleProgress))
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
            <span>
                {adGeneration.status === 'assembling' 
                    ? 'Stitching Video...' 
                    : `Generating Scenes (${adGeneration.clips?.filter((c:any) => c.status === 'completed').length || 0}/${adGeneration.clips?.length || 12})`
                }
            </span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
             <div 
               className="bg-indigo-600 h-full transition-all duration-500 ease-out"
               style={{ width: `${progress}%` }}
             ></div>
          </div>
          
          {/* Status Dots */}
          <div className="mt-4 grid grid-cols-6 sm:grid-cols-12 gap-2">
            {adGeneration.clips?.map((clip: any, idx: number) => (
               <div 
                 key={idx} 
                 title={`Scene ${idx+1}: ${clip.status}`}
                 className={`h-2 rounded-full transition-colors duration-300 ${
                 clip.status === 'completed' ? 'bg-green-500' : 
                 clip.status === 'generating' ? 'bg-indigo-400 animate-pulse' : 
                 clip.status === 'failed' ? 'bg-red-500' : 
                 'bg-gray-200'
               }`} />
            ))}
          </div>
          
          <p className="text-center text-sm text-gray-500 mt-4">
            This process generates 12 unique video clips. It typically takes 5-10 minutes.
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
              className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 shadow-md transition-all hover:scale-105"
            >
              Download Video
            </a>
          </div>
        </div>
      ) : adGeneration.status === 'failed' ? (
        <div className="text-center text-red-600 p-6 bg-red-50 rounded-lg border border-red-200">
          <p className="font-semibold">Generation failed.</p>
          <p className="text-sm mt-2">Please check the console logs for details or try again.</p>
        </div>
      ) : null}
    </div>
  )
}