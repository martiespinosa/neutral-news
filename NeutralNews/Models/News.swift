//
//  News.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import Foundation

struct News: Codable, Identifiable {
    var id = UUID()
    let title: String
    let description: String
    let category: String
    let imageUrl: String?
    let link: String
    let pubDate: String
    let sourceMedium: Media
    var group: Int?
    
    static let mock = News(
        title: "Lorem ipsum dolor sit amet",
        description: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        category: "Category",
        imageUrl: nil,
        link: "Link",
        pubDate: "PubDate",
        sourceMedium: .abc,
        group: nil
    )
}
