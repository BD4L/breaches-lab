import React, { useState, useEffect } from 'react'
import { Users, X } from 'lucide-react'
import { Button } from '../ui/Button'

interface NumericSliderProps {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  formatValue?: (value: number) => string
}

export function NumericSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 100000,
  step = 100,
  formatValue = (val) => val.toLocaleString()
}: NumericSliderProps) {
  const [sliderValue, setSliderValue] = useState(value)

  useEffect(() => {
    setSliderValue(value)
  }, [value])

  const handleSliderChange = (newValue: number) => {
    setSliderValue(newValue)
    onChange(newValue)
  }

  const handleClear = () => {
    setSliderValue(0)
    onChange(0)
  }

  const hasValue = sliderValue > 0

  // Predefined quick values with impact levels
  const quickValues = [
    { label: 'Any', value: 0, color: 'gray' },
    { label: '100+', value: 100, color: 'green' },
    { label: '500+', value: 500, color: 'green' },
    { label: '1K+', value: 1000, color: 'yellow' },
    { label: '5K+', value: 5000, color: 'yellow' },
    { label: '10K+', value: 10000, color: 'orange' },
    { label: '50K+', value: 50000, color: 'red' },
    { label: '100K+', value: 100000, color: 'red' },
    { label: '500K+', value: 500000, color: 'purple' },
    { label: '1M+', value: 1000000, color: 'purple' },
  ]

  const getColorClasses = (color: string, isSelected: boolean) => {
    if (isSelected) {
      switch (color) {
        case 'green': return 'bg-green-600 text-white border-green-600'
        case 'yellow': return 'bg-yellow-600 text-white border-yellow-600'
        case 'orange': return 'bg-orange-600 text-white border-orange-600'
        case 'red': return 'bg-red-600 text-white border-red-600'
        case 'purple': return 'bg-purple-600 text-white border-purple-600'
        default: return 'bg-blue-600 text-white border-blue-600'
      }
    } else {
      switch (color) {
        case 'green': return 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800 dark:hover:bg-green-900/30'
        case 'yellow': return 'bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100 dark:bg-yellow-900/20 dark:text-yellow-300 dark:border-yellow-800 dark:hover:bg-yellow-900/30'
        case 'orange': return 'bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800 dark:hover:bg-orange-900/30'
        case 'red': return 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800 dark:hover:bg-red-900/30'
        case 'purple': return 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-800 dark:hover:bg-purple-900/30'
        default: return 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600'
      }
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          <Users className="inline w-4 h-4 mr-1" />
          {label}
        </label>
        {hasValue && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="p-1 h-6 w-6 text-gray-400 hover:text-gray-600"
          >
            <X className="w-3 h-3" />
          </Button>
        )}
      </div>

      {/* Quick Value Buttons */}
      <div className="space-y-2">
        <div className="text-xs text-gray-500 dark:text-gray-400">Quick Select:</div>
        <div className="flex flex-wrap gap-1">
          {quickValues.map((quick) => {
            const isSelected = sliderValue === quick.value
            return (
              <button
                key={quick.value}
                onClick={() => handleSliderChange(quick.value)}
                className={`px-2 py-1 text-xs rounded-md border transition-all duration-200 font-medium ${
                  getColorClasses(quick.color, isSelected)
                }`}
                title={quick.value === 0 ? 'Show all breaches' : `Show breaches affecting ${quick.value.toLocaleString()}+ people`}
              >
                {quick.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Custom Slider */}
      <div className="space-y-2">
        <div className="relative">
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={sliderValue}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg cursor-pointer dark:bg-gray-700"
            style={{
              WebkitAppearance: 'none',
              appearance: 'none',
              background: 'transparent',
              outline: 'none'
            }}
          />
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
            <span>{formatValue(min)}</span>
            <span>{formatValue(max)}</span>
          </div>
        </div>

        {hasValue && (
          <div className="text-center">
            <div className="inline-flex items-center space-x-2 px-3 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 border border-blue-200 dark:border-blue-800 rounded-lg">
              <span className="text-lg"></span>
              <div className="text-left">
                <div className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  Alert Threshold
                </div>
                <div className="text-xs text-blue-600 dark:text-blue-300">
                  {formatValue(sliderValue)}+ people affected
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <style dangerouslySetInnerHTML={{
        __html: `
          input[type="range"]::-webkit-slider-track {
            height: 8px;
            border-radius: 4px;
            background: #e5e7eb;
            border: none;
          }

          input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: #2563eb;
            cursor: grab;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
            margin-top: -6px;
          }

          input[type="range"]::-webkit-slider-thumb:hover {
            background: #1d4ed8;
            transform: scale(1.1);
          }

          input[type="range"]::-webkit-slider-thumb:active {
            cursor: grabbing;
          }

          input[type="range"]::-moz-range-track {
            height: 8px;
            border-radius: 4px;
            background: #e5e7eb;
            border: none;
          }

          input[type="range"]::-moz-range-thumb {
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: #2563eb;
            cursor: grab;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
          }

          input[type="range"]::-moz-range-thumb:hover {
            background: #1d4ed8;
          }
        `
      }} />
    </div>
  )
}
