//
//  Relevance.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 5/5/25.
//

import Foundation

enum Relevance: Int, CaseIterable {
    case veryLow = 1
    case low = 2
    case medium = 3
    case high = 4
    case veryHigh = 5
    
    var description: String {
        switch self {
        case .veryLow: return "Muy baja"
        case .low: return "Baja"
        case .medium: return "Media"
        case .high: return "Alta"
        case .veryHigh: return "Muy alta"
        }
    }
}
