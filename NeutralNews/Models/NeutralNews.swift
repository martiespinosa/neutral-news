//
//  NeutralNews.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 13/4/25.
//

import Foundation

struct NeutralNews: Codable, Identifiable {
    var id = UUID().uuidString
    let neutralTitle: String
    let neutralDescription: String
    let category: String
    let imageUrl: String?
//    let date: String
    var group: Int
    
    static let mock = NeutralNews(
        neutralTitle: "Lorem ipsum dolor sit amet",
        neutralDescription: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        category: "Category",
        imageUrl: nil,
//        date: "date",
        group: 0
    )
}
