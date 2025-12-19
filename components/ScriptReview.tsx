'use client'

import { useState } from 'react'
import { ScriptData, Scene } from '@/types'

interface ScriptReviewProps {
  script: ScriptData
  onApprove: (script: ScriptData) => void
  onBack: () => void
}

export default function ScriptReview({ script, onApprove, onBack }: ScriptReviewProps) {
  const [editedScript, setEditedScript] = useState<ScriptData>(script)
  const [editingScene, setEditingScene] = useState<number | null>(null)

  const handleSceneEdit = (sceneId: number, field: keyof Scene, value: string) => {
    setEditedScript({
      ...editedScript,
      scenes: editedScript.scenes.map(s =>
        s.id === sceneId ? { ...s, [field]: value } : s
      ),
    })
  }

  // Removed handleToneChange

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold text-gray-800">Review Script (UGC Mode)</h2>
        <button
          onClick={onBack}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          ← Back
        </button>
      </div>

      <div className="mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Product Name
          </label>
          <input
            type="text"
            value={editedScript.product_name}
            onChange={(e) => setEditedScript({ ...editedScript, product_name: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Master Description
          </label>
          <textarea
            value={editedScript.master_description}
            onChange={(e) => setEditedScript({ ...editedScript, master_description: e.target.value })}
            rows={3}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>
        
        {/* Removed Tone Selection UI */}
      </div>

      <div className="space-y-6 mb-8">
        <h3 className="text-xl font-semibold text-gray-800">Scenes</h3>
        {editedScript.scenes.map((scene, index) => (
          <div key={scene.id} className="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors">
            <div className="flex justify-between items-start mb-2">
              <span className="font-medium text-gray-600">Scene {index + 1}</span>
              <span className="text-xs px-2 py-1 bg-gray-100 rounded text-gray-500 uppercase">
                {scene.role}
              </span>
            </div>
            
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Visual Prompt</label>
                <textarea
                  value={scene.prompt}
                  onChange={(e) => handleSceneEdit(scene.id, 'prompt', e.target.value)}
                  className="w-full text-sm p-2 border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                  rows={3}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-4">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={() => onApprove(editedScript)}
          className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-md"
        >
          Generate Video (UGC)
        </button>
      </div>
    </div>
  )
}