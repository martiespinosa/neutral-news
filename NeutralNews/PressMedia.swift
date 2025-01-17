//
//  PressMedia.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/5/25.
//

import Foundation
import SwiftUICore

struct PressMedia: Decodable {
    let name: String
    let link: String
    
    static let mock = PressMedia(
        name: "El País",
        link: "https://www.elpais.com"
    )
}

enum Media: CaseIterable {
    case abc
    case elPais
    case rtve
    
    var pressMedia: PressMedia {
        switch self {
        case .abc: PressMedia(
            name: "ABC",
            link: "https://www.abc.es/rss/2.0/portada/"
        )
        case .elPais: PressMedia(
            name: "El País",
            link: "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"
        )
        case .rtve: PressMedia(
            name: "RTVE",
            link: "https://api2.rtve.es/rss/temas_noticias.xml"
        )
        }
    }
}

extension String {
    /// Normalizes the name of the media by converting it to lowercase, removing diacritical marks (accents),
    /// replacing spaces with hyphens, and removing non-alphanumeric characters.
    /// This is used to match the media name with the corresponding logo and color in the catalog.
    ///
    /// - Returns: A normalized version of the media name, in lowercase and without accents, spaces, or special characters.
    func normalized() -> String {
        return self
            .lowercased()
            .folding(options: .diacriticInsensitive, locale: .current)
            .replacingOccurrences(of: " ", with: "-")
            .filter { $0.isLetter || $0.isNumber || $0 == "-" }
    }
}
