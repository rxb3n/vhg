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

  const handleToneChange = (tone: 'UGC' | 'premium' | 'playful') => {
    setEditedScript({ ...editedScript, tone })
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold text-gray-800">Review Script</h2>
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

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Tone
          </label>
          <div className="flex gap-4">
            {(['UGC', 'premium', 'playful'] as const).map((tone) => (
              <button
                key={tone}
                onClick={() => handleToneChange(tone)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  editedScript.tone === tone
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {tone.charAt(0).toUpperCase() + tone.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Scenes ({editedScript.scenes.length} × 5 seconds)
        </h3>
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {editedScript.scenes.map((scene) => (
            <div
              key={scene.id}
              className="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors"
            >
              <div className="flex justify-between items-start mb-2">
                <span className="font-semibold text-indigo-600">Scene {scene.id}</span>
                <button
                  onClick={() => setEditingScene(editingScene === scene.id ? null : scene.id)}
                  className="text-sm text-indigo-600 hover:text-indigo-800"
                >
                  {editingScene === scene.id ? 'Collapse' : 'Edit'}
                </button>
              </div>
              
              <div className="mb-2">
                <span className="text-sm text-gray-600">Action: </span>
                <span className="text-sm font-medium">{scene.action}</span>
              </div>

              {editingScene === scene.id && (
                <div className="mt-3 space-y-3 pt-3 border-t border-gray-200">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Action
                    </label>
                    <input
                      type="text"
                      value={scene.action}
                      onChange={(e) => handleSceneEdit(scene.id, 'action', e.target.value)}
                      className="w-full px-3 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Prompt
                    </label>
                    <textarea
                      value={scene.prompt}
                      onChange={(e) => handleSceneEdit(scene.id, 'prompt', e.target.value)}
                      rows={3}
                      className="w-full px-3 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  {scene.role && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Role
                      </label>
                      <input
                        type="text"
                        value={scene.role}
                        onChange={(e) => handleSceneEdit(scene.id, 'role', e.target.value)}
                        className="w-full px-3 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  )}
                </div>
              )}

              <div className="mt-2">
                <p className="text-xs text-gray-500 line-clamp-2">{scene.prompt}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-4">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={() => onApprove(editedScript)}
          className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Generate Video
        </button>
      </div>
    </div>
  )
}

