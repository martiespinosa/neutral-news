//
//  NewsRowView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct NewsRowView: View {
    let news: News
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(news.category.uppercased())
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            
            Text(news.title)
                .font(.headline)
                .lineLimit(2)
            
            Text(news.description)
                .foregroundStyle(.secondary)
                .lineLimit(4)
                .padding(.top, 8)
            
            HStack {
                Text(news.sourceMedium.name)
                
                Spacer()
                
                Button("Leer más") { }
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.capsule)
                    .controlSize(.small)
            }
            .padding(.top, 8)
        }
    }
}

#Preview {
    NewsRowView(news: News.mock)
        .padding()
}
