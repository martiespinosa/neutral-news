//
//  DayInfo.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 4/5/25.
//

import Foundation

struct DayInfo: Identifiable, Hashable {
    let id = UUID()
    let dayName: String
    let dayNumber: Int
    let monthName: String
    let date: Date
    
    var formattedDate: String {
        "\(dayName), \(dayNumber) de \(monthName)"
    }
    
    var shortFormat: String {
        switch dayName {
        case "Hoy", "Ayer":
            return dayName
        default:
            return "\(dayName) \(dayNumber)"
        }
    }
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(date)
    }
    
    static func == (lhs: DayInfo, rhs: DayInfo) -> Bool {
        Calendar.current.isDate(lhs.date, inSameDayAs: rhs.date)
    }
    
    static let today: DayInfo = {
        let calendar = Calendar.current
        let dayFormatter = DateFormatter()
        let monthFormatter = DateFormatter()
        
        return DayInfo(
            dayName: "Hoy",
            dayNumber: calendar.component(.day, from: .now),
            monthName: monthFormatter.string(from: .now),
            date: .now
        )
    }()
}
