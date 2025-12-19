'use client'

import { useState } from 'react'
import ImageUpload from '@/components/ImageUpload'
import ScriptReview from '@/components/ScriptReview'
import VideoPreview from '@/components/VideoPreview'
import { ScriptData, AdGeneration } from '@/types'

export default function Home() {
  const [currentStep, setCurrentStep] = useState<'upload' | 'review' | 'generating' | 'preview'>('upload')
  const [scriptData, setScriptData] = useState<ScriptData | null>(null)
  const [adGeneration, setAdGeneration] = useState<AdGeneration | null>(null)
  const [productImage, setProductImage] = useState<string | null>(null)
  const [clips, setClips] = useState<any[]>([])
  const [generationStatus, setGenerationStatus] = useState<string>('pending')

  const handleImageUploaded = (imageUrl: string, script: ScriptData) => {
    setProductImage(imageUrl)
    setScriptData(script)
    setCurrentStep('review')
  }

  const handleScriptApproved = async (approvedScript: ScriptData) => {
    setScriptData(approvedScript)
    setCurrentStep('generating')
    
      // Start video generation
      try {
        // Extract relative path from full URL if needed
        let imageUrlToSend = productImage
        if (productImage.startsWith('http://localhost:8000')) {
          imageUrlToSend = productImage.replace('http://localhost:8000', '')
        }
        
        const response = await fetch('http://localhost:8000/api/generate-video', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ script: approvedScript, imageUrl: imageUrlToSend }),
        })
      
      if (!response.ok) throw new Error('Failed to start generation')
      
      const data = await response.json()
      setAdGeneration(data)
      
      // Poll for completion
      pollGenerationStatus(data.id)
    } catch (error) {
      console.error('Error starting generation:', error)
      alert('Failed to start video generation')
      setCurrentStep('review')
    }
  }

  const pollGenerationStatus = async (adId: string) => {
    let attempts = 0
    let consecutiveErrors = 0
    const maxAttempts = 600 // 30 minutes max (600 * 3 seconds)
    const maxConsecutiveErrors = 5 // Stop after 5 consecutive errors
    
    const interval = setInterval(async () => {
      attempts++
      
      // Timeout after max attempts
      if (attempts > maxAttempts) {
        clearInterval(interval)
        alert('Video generation timed out. Please try again.')
        setCurrentStep('review')
        return
      }
      
      try {
        // Create a timeout promise
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout')), 5000)
        )
        
        const fetchPromise = fetch(`http://localhost:8000/api/generation-status/${adId}`)
        const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
        
        if (!response.ok) {
          console.error(`Status check failed: ${response.status}`)
          consecutiveErrors++
          if (response.status >= 500) {
            // Server error - backend might be down
            console.error('Backend server error. Check if backend is running.')
          }
          if (consecutiveErrors >= maxConsecutiveErrors) {
            clearInterval(interval)
            alert('Lost connection to backend server. Please check if the backend is running.')
            setCurrentStep('review')
            return
          }
          return
        }
        
        // Reset error counter on success
        consecutiveErrors = 0
        
        const data = await response.json()
        
        // Debug logging
        console.log('Status update:', {
          status: data.status,
          clipsCount: data.clips?.length || 0,
          completedClips: data.clips?.filter((c: any) => c.status === 'completed').length || 0,
          clips: data.clips
        })
        
        // Update clips and status for progress display
        if (data.clips) {
          setClips(data.clips)
        }
        setGenerationStatus(data.status || 'pending')
        
        if (data.status === 'completed') {
          clearInterval(interval)
          setAdGeneration(data)
          setCurrentStep('preview')
        } else if (data.status === 'failed') {
          clearInterval(interval)
          alert('Video generation failed. Please check the console for details.')
          setCurrentStep('review')
        } else if (data.status === 'assembling') {
          // Keep polling, but we know we're in assembly phase
          console.log('Assembling final video...')
        }
        // For "pending" and "generating", continue polling
      } catch (error: any) {
        console.error('Error polling status:', error)
        consecutiveErrors++
        
        // Check if it's a network/connection error
        const isNetworkError = 
          error.name === 'AbortError' || 
          error.name === 'TypeError' || 
          error.message?.includes('Failed to fetch') ||
          error.message?.includes('Request timeout') ||
          error.message?.includes('NetworkError')
        
        if (isNetworkError) {
          console.error('Backend connection failed. Backend may be down.')
          if (consecutiveErrors >= maxConsecutiveErrors) {
            clearInterval(interval)
            alert('Lost connection to backend server. Please check if the backend is running and try again.')
            setCurrentStep('review')
            return
          }
        } else {
          // For other errors, continue polling but log them
          if (consecutiveErrors >= maxConsecutiveErrors) {
            console.error('Too many consecutive errors. Stopping.')
            clearInterval(interval)
            alert('Failed to get status updates. Please check the console for details.')
            setCurrentStep('review')
            return
          }
        }
      }
    }, 3000) // Poll every 3 seconds
  }

  return (
    <main className="min-h-screen p-8 bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-center mb-8 text-gray-800">
          Viral Hook Generator
        </h1>
        
        {currentStep === 'upload' && (
          <ImageUpload onUploaded={handleImageUploaded} />
        )}
        
        {currentStep === 'review' && scriptData && (
          <ScriptReview 
            script={scriptData} 
            onApprove={handleScriptApproved}
            onBack={() => setCurrentStep('upload')}
          />
        )}
        
        {currentStep === 'generating' && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto mb-4"></div>
            <p className="text-xl text-gray-700">Generating your viral video hook...</p>
            <p className="text-sm text-gray-500 mt-2">This may take a few minutes</p>
            
            {/* Progress indicator */}
            <div className="mt-6 max-w-md mx-auto">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Status: {generationStatus}</span>
                <span>
                  {clips.length > 0 ? (
                    `${clips.filter(c => c.status === 'completed').length} / ${clips.length} clips`
                  ) : (
                    'Initializing...'
                  )}
                </span>
              </div>
              {clips.length > 0 ? (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                    style={{ 
                      width: `${Math.min(100, (clips.filter(c => c.status === 'completed').length / clips.length) * 100)}%` 
                    }}
                  ></div>
                </div>
              ) : (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-gray-300 h-2 rounded-full" style={{ width: '0%' }}></div>
                </div>
              )}
              {generationStatus === 'assembling' && (
                <p className="text-sm text-indigo-600 mt-2">Assembling final video...</p>
              )}
              {/* Debug info */}
              <p className="text-xs text-gray-400 mt-2">
                Clips in state: {clips.length} | 
                Completed: {clips.filter(c => c.status === 'completed').length} |
                Generating: {clips.filter(c => c.status === 'generating').length} |
                Pending: {clips.filter(c => c.status === 'pending').length}
              </p>
            </div>
          </div>
        )}
        
        {currentStep === 'preview' && adGeneration && (
          <VideoPreview adGeneration={adGeneration} />
        )}
      </div>
    </main>
  )
}

