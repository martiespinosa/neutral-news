//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI

struct NewsView: View {
    let news: [News]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(news.first?.title ?? "")
                    .font(.title)
                    .fontWeight(.semibold)
                
                Text(news.first?.description ?? "")
            }
            .padding()
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(news) { new in
                        MediaHeadlineView(news: new)
                    }
                }
                .padding(.leading, 16)
            }
        }
        .scrollBounceBehavior(.basedOnSize)
    }
}

#Preview {
    NewsView(news: [.mock, .mock, .mock])
}
