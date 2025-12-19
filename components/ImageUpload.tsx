'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { ScriptData } from '@/types'

interface ImageUploadProps {
  onUploaded: (imageUrl: string, script: ScriptData) => void
}

export default function ImageUpload({ onUploaded }: ImageUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploading(true)
    setPreview(URL.createObjectURL(file))

    const formData = new FormData()
    formData.append('image', file)

    try {
      const response = await fetch('http://localhost:8000/api/analyze-product', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Failed to analyze product')
      }

      const data = await response.json()
      // Convert relative URL to absolute for display
      const imageUrl = data.imageUrl.startsWith('http') 
        ? data.imageUrl 
        : `http://localhost:8000${data.imageUrl}`
      onUploaded(imageUrl, data.script)
    } catch (error) {
      console.error('Upload error:', error)
      alert('Failed to upload and analyze image')
      setPreview(null)
    } finally {
      setUploading(false)
    }
  }, [onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.webp']
    },
    maxFiles: 1,
    disabled: uploading
  })

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Upload Product Image</h2>
      
      {preview ? (
        <div className="text-center">
          <img 
            src={preview} 
            alt="Preview" 
            className="max-w-md mx-auto rounded-lg shadow-md mb-4"
          />
          {uploading && (
            <div className="mt-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
              <p className="mt-2 text-gray-600">Analyzing product...</p>
            </div>
          )}
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-indigo-500 bg-indigo-50'
              : 'border-gray-300 hover:border-indigo-400'
          } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <input {...getInputProps()} />
          <div className="space-y-4">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div>
              <p className="text-lg text-gray-700">
                {isDragActive
                  ? 'Drop the image here'
                  : 'Drag & drop an image here, or click to select'}
              </p>
              <p className="text-sm text-gray-500 mt-2">
                PNG, JPG, WEBP up to 10MB
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

